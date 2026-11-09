from pathlib import Path
import re
from typing import Any

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rag import PDFStore, answer_with_context


ROOT = Path(__file__).parent
PDF_DIR = ROOT
store = PDFStore(PDF_DIR)
store.ingest()


class LocalRAG:
    def __init__(self, source_dir: Any = None) -> None:
        self.source_dir = Path(source_dir) if source_dir is not None else ROOT
        self.store = PDFStore(self.source_dir)
        self._built = False

    def build(self) -> int:
        result = self.store.ingest()
        self._built = True
        return result.get("chunks", len(self.store.chunks))

    def search(self, query: str, top_k: int = 5):
        if not self._built:
            self.build()
        return self.store.search(query, limit=top_k)


app = FastAPI(title="Papertrail RAG")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/status")
def status() -> dict[str, int]:
    return {"documents": len({chunk.filename for chunk in store.chunks}), "chunks": len(store.chunks)}


@app.get("/api/library")
def library() -> dict[str, list[str]]:
    return {"files": sorted({chunk.filename for chunk in store.chunks})}


@app.post("/api/ingest")
async def ingest(files: list[UploadFile] = File(default=[])) -> dict[str, int]:
    for upload in files:
        if upload.filename and upload.filename.lower().endswith(".pdf"):
            (PDF_DIR / Path(upload.filename).name).write_bytes(await upload.read())
    return store.ingest()


@app.post("/api/ask")
def ask(payload: dict[str, Any]) -> dict[str, object]:
    raw_query = payload.get("query", "")
    query = raw_query.strip() if isinstance(raw_query, str) else ""
    if not query:
        return {"answer": "Ask a question about your PDFs to get started.", "sources": []}

    retrieval_query = query
    history = payload.get("history", [])
    if isinstance(history, list):
        previous_user_questions = [
            turn.get("content", "").strip()
            for turn in history[:-1]
            if isinstance(turn, dict)
            and turn.get("role") == "user"
            and isinstance(turn.get("content"), str)
            and turn.get("content", "").strip()
        ]
        follow_up = len(query.split()) <= 8 and bool(
            re.search(r"\b(it|they|them|those|these|that|there|also|more|why)\b", query, re.I)
        )
        if follow_up and previous_user_questions:
            combined_terms = dict.fromkeys(
                f"{previous_user_questions[-1]} {query}".split()
            )
            retrieval_query = " ".join(combined_terms)

    sources = store.search(retrieval_query)
    return {"answer": answer_with_context(sources), "sources": sources}
