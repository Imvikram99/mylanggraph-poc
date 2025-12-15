"""Basic RAG node placeholder."""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console

console = Console()


class RAGNode:
    """Retrieve + generate answer from dense vector store."""

    def __init__(self) -> None:
        pass

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        query = _last_user_content(state.get("messages", []))
        retrieved_docs = _fake_retrieve(query)
        answer = _compose_answer(query, retrieved_docs)
        state.setdefault("artifacts", []).extend(retrieved_docs)
        state["output"] = answer
        state.setdefault("messages", []).append({"role": "assistant", "content": answer})
        console.log(f"[cyan]RAGNode[/] answered query with {len(retrieved_docs)} docs")
        return state


def _fake_retrieve(query: str) -> List[str]:
    if not query:
        return []
    return [
        f"Doc snippet A supporting '{query}'",
        f"Doc snippet B referencing '{query}'",
    ]


def _compose_answer(query: str, docs: List[str]) -> str:
    context = "\n".join(f"- {doc}" for doc in docs)
    return f"Answer for: {query}\nContext:\n{context}"


def _last_user_content(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
