"""Production RAG node backed by the configured vector store."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rich.console import Console

from ...services import RetrievedDocument, VectorStoreRetriever
from ..messages import append_message

console = Console()


class RAGNode:
    """Retrieve + synthesize answer grounded in the vector store."""

    def __init__(self, retriever: Optional[VectorStoreRetriever] = None) -> None:
        self.retriever = retriever or VectorStoreRetriever()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        query = _last_user_content(state.get("messages", []))
        retrieved_docs = self.retriever.search(query, top_k=6)
        answer = _compose_answer(query, retrieved_docs)
        state.setdefault("artifacts", []).extend(
            [{"text": doc.text, "metadata": doc.metadata, "score": doc.score} for doc in retrieved_docs]
        )
        state["output"] = answer
        append_message(state, "assistant", answer)
        console.log(f"[cyan]RAGNode[/] answered query with {len(retrieved_docs)} supporting docs")
        return state


def _compose_answer(query: str, docs: List[RetrievedDocument]) -> str:
    if not query:
        return "No question received."
    if not docs:
        return f"I could not retrieve any supporting passages for '{query}'. Consider running ingestion again."
    highlights = []
    for idx, doc in enumerate(docs, start=1):
        snippet = doc.text.strip()
        source = doc.metadata.get("source") or doc.metadata.get("path") or doc.metadata.get("document_id", "unknown")
        highlights.append(f"[{idx}] {snippet} (source: {source})")
    context = "\n".join(highlights)
    return f"Question: {query}\n\nKey evidence:\n{context}"


def _last_user_content(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
