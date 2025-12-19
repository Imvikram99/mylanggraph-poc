"""GraphRAG node that walks a lightweight knowledge graph."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rich.console import Console

from ...services import GraphKnowledgeBase
from ..messages import append_message

console = Console()


class GraphRAGNode:
    """Traverse the knowledge graph around detected entities."""

    def __init__(self, kb: Optional[GraphKnowledgeBase] = None) -> None:
        self.kb = kb or GraphKnowledgeBase()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        metadata = state.setdefault("metadata", {})
        try:
            query = _last_user_content(state.get("messages", []))
            entities = _extract_entities(query)
            hops = self.kb.neighbors_descriptions(entities) if self.kb else []
            answer = _compose_summary(query, entities, hops)
            state.setdefault("artifacts", []).extend(hops if isinstance(hops, list) else [])
            state["output"] = answer
            append_message(state, "assistant", answer)
            metadata["graph_rag_status"] = "ok"
            console.log(f"[magenta]GraphRAG[/] handled query with {len(entities)} entities, {len(hops)} hops")
        except Exception as exc:  # pragma: no cover - defensive fallback
            metadata["graph_rag_status"] = "error"
            metadata["graph_rag_error"] = str(exc)
            error_msg = f"Graph traversal failed ({exc}); falling back to RAG."
            console.log(f"[red]GraphRAG error[/] {exc}")
            append_message(state, "assistant", error_msg)
            state["output"] = error_msg
        return state

    def branch(self, state: Dict[str, Any]) -> str:
        status = (state.get("metadata") or {}).get("graph_rag_status", "ok")
        return "ok" if status == "ok" else "fallback"


def _extract_entities(query: str) -> List[str]:
    words = [token.strip(",.") for token in (query or "").split()]
    entities: List[str] = []
    current: List[str] = []
    for token in words:
        if token.istitle():
            current.append(token)
        elif current:
            entities.append(" ".join(current))
            current = []
    if current:
        entities.append(" ".join(current))
    return entities


def _compose_summary(query: str, entities: List[str], hops: List[str]) -> str:
    if not query:
        return "No question received."
    if not entities:
        return f"Could not detect named entities in '{query}'."
    if not hops:
        return f"No graph connections found for {', '.join(entities)}. Consider enriching data/graph/entities.json."
    path = "\n".join(f"* {hop}" for hop in hops)
    return f"Graph summary for '{query}' (entities: {', '.join(entities)}):\n{path}"


def _last_user_content(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
