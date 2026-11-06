# test_adapter.py

from functools import lru_cache
from pathlib import Path

from rag import PDFStore, answer_with_context


@lru_cache(maxsize=1)
def get_rag() -> PDFStore:
    """
    Build the RAG index once and reuse it for all tests.
    """
    rag = PDFStore(Path(__file__).resolve().parent)
    rag.ingest()
    return rag


def retrieve(question: str, top_k: int = 5):
    """
    Test only the retrieval component of the RAG system.
    """

    if not isinstance(question, str):
        raise TypeError("Question must be a string.")

    question = question.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    rag = get_rag()

    return rag.search(
        question,
        limit=top_k,
    )


def ask_chatbot(question: str, top_k: int = 5) -> str:
    """
    Run the complete RAG pipeline:
    retrieval + answer generation.
    """

    results = retrieve(
        question,
        top_k=top_k
    )

    return answer_with_context(results)