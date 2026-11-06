from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from math import log, sqrt
from pathlib import Path
from typing import Any

from pypdf import PdfReader


_STOP_WORDS = frozenset(
    "a about above after again against all am an and any are as at be because been "
    "before being below between both but by can did do does doing down during each "
    "few for from further had has have having he her here hers herself him himself "
    "his how i if in into is it its itself just me more most my myself no nor not of "
    "off on once only or other our ours ourselves out over own same she should so "
    "some such than that the their theirs them themselves then there these they "
    "this those through to too under until up very was we were what when where which "
    "while who whom why will with you your yours yourself yourselves"
    .split()
)


def _terms(text: str) -> list[str]:
    words = [
        word
        for word in re.findall(r"(?u)\b\w\w+\b", text.lower())
        if word not in _STOP_WORDS
    ]
    return words + [f"{left} {right}" for left, right in zip(words, words[1:])]


def _repair_spaced_letters(text: str) -> str:
    """Join character-spaced PDF lines while leaving ordinary text unchanged."""
    repaired_lines = []
    for line in text.splitlines():
        spaced_runs = list(re.finditer(r"(?<!\S)[A-Za-z](?: [A-Za-z]){3,}(?!\S)", line))
        spaced_letters = sum(len(match.group().split()) for match in spaced_runs)
        letter_count = sum(character.isalpha() for character in line)
        if letter_count >= 12 and spaced_letters / letter_count >= 0.55:
            for match in reversed(spaced_runs):
                joined = match.group().replace(" ", "")
                line = line[:match.start()] + joined + line[match.end():]
        repaired_lines.append(line)
    return "\n".join(repaired_lines)


class TfidfVectorizer:
    """Small pure-Python TF-IDF vectorizer with L2-normalized output."""

    def __init__(self) -> None:
        self.idf: dict[str, float] = {}

    @staticmethod
    def _vectorize(terms: list[str], idf: dict[str, float]) -> dict[str, float]:
        counts = Counter(term for term in terms if term in idf)
        vector = {term: count * idf[term] for term, count in counts.items()}
        norm = sqrt(sum(value * value for value in vector.values()))
        if norm:
            vector = {term: value / norm for term, value in vector.items()}
        return vector

    def fit_transform(self, documents: list[str]) -> list[dict[str, float]]:
        document_terms = [_terms(document) for document in documents]
        document_frequency = Counter(
            term for terms in document_terms for term in set(terms)
        )
        document_count = len(document_terms)
        self.idf = {
            term: 1.0 + log((1 + document_count) / (1 + frequency))
            for term, frequency in document_frequency.items()
        }
        return [self._vectorize(terms, self.idf) for terms in document_terms]

    def transform(self, documents: list[str]) -> list[dict[str, float]]:
        return [self._vectorize(_terms(document), self.idf) for document in documents]


@dataclass
class Chunk:
    text: str
    filename: str
    page: int


class PDFStore:
    def __init__(self, source_dir: Path) -> None:
        self.source_dir = source_dir
        self.chunks: list[Chunk] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix: Any = None

    def ingest(self) -> dict[str, int]:
        chunks: list[Chunk] = []
        for pdf_path in sorted(path for path in self.source_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"):
            try:
                reader = PdfReader(str(pdf_path))
            except Exception:
                continue
            for page_number, page in enumerate(reader.pages, start=1):
                text = _repair_spaced_letters((page.extract_text() or "").strip())
                for part in self._chunk(text):
                    chunks.append(Chunk(part, pdf_path.name, page_number))
        self.chunks = chunks
        if chunks:
            self.vectorizer = TfidfVectorizer()
            self.matrix = self.vectorizer.fit_transform(
                [f"{chunk.filename} {chunk.text}" for chunk in chunks]
            )
        else:
            self.vectorizer = None
            self.matrix = None
        return {"documents": len({chunk.filename for chunk in chunks}), "chunks": len(chunks)}

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self.chunks or self.vectorizer is None:
            return []
        query_vector = self.vectorizer.transform([query])[0]
        query_title_terms = {
            term
            for term in re.findall(r"(?u)\b\w{4,}\b", query.lower())
            if term not in _STOP_WORDS and term not in {"report", "document"}
        }
        scores = [
            sum(weight * document.get(term, 0.0) for term, weight in query_vector.items())
            + 0.08 * len(
                query_title_terms
                & set(re.findall(r"(?u)\b\w{4,}\b", chunk.filename.lower()))
            )
            for chunk, document in zip(self.chunks, self.matrix)
        ]
        results = []
        for index in sorted(range(len(scores)), key=scores.__getitem__, reverse=True):
            score = scores[index]
            if score <= 0:
                continue
            chunk = self.chunks[index]
            results.append({"text": chunk.text, "filename": chunk.filename, "page": chunk.page, "score": round(score, 4)})
            if len(results) == limit:
                break
        return results

    @staticmethod
    def _chunk(text: str, words_per_chunk: int = 180, overlap: int = 35) -> list[str]:
        words = re.findall(r"\S+", text)
        if not words:
            return []
        chunks = []
        step = words_per_chunk - overlap
        for start in range(0, len(words), step):
            part = " ".join(words[start : start + words_per_chunk]).strip()
            if len(part) >= 80:
                chunks.append(part)
            if start + words_per_chunk >= len(words):
                break
        return chunks


def answer_with_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return "I couldn't find relevant passages in the indexed PDFs. Try a more specific question or add another document."
    return " ".join(re.split(r"(?<=[.!?])\s+", result["text"])[0] for result in results[:3])
