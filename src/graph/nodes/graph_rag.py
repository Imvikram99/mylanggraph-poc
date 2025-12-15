"""GraphRAG node placeholder."""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console

console = Console()


class GraphRAGNode:
    """Simulate traversing a graph of entities and summarizing results."""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        query = _last_user_content(state.get("messages", []))
        entities = _extract_entities(query)
        hops = _walk_graph(entities)
        answer = _compose_summary(query, hops)
        state.setdefault("artifacts", []).extend(hops)
        state["output"] = answer
        state.setdefault("messages", []).append({"role": "assistant", "content": answer})
        console.log(f"[magenta]GraphRAG[/] handled query with {len(entities)} entities")
        return state


def _extract_entities(query: str) -> List[str]:
    tokens = [token.strip(",.") for token in query.split() if token.istitle()]
    return tokens or ["Agent", "Memory"]


def _walk_graph(entities: List[str]) -> List[str]:
    return [f"{entity} -> MemoryStrategy -> Collaboration" for entity in entities]


def _compose_summary(query: str, hops: List[str]) -> str:
    path = "\n".join(f"* {hop}" for hop in hops)
    return f"Graph summary for '{query}':\n{path}"


def _last_user_content(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
