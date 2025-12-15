"""Router node selecting downstream path."""

from __future__ import annotations

import re
from typing import Any, Dict

from rich.console import Console

console = Console()


class RouterNode:
    """Heuristic router that chooses between RAG, GraphRAG, skills, or swarm."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        route = self.decide_route(state)
        state["route"] = route
        state.setdefault("metadata", {}).setdefault("route_history", []).append(route)
        console.log(f"[bold]Router[/] selected route={route}")
        return state

    def decide_route(self, state: Dict[str, Any]) -> str:
        messages = state.get("messages", [])
        last = (messages[-1] if messages else {})
        content = str(last.get("content", "")).lower()
        if any(keyword in content for keyword in ["graph", "relationship", "collaborate"]):
            return "graph_rag"
        if any(keyword in content for keyword in ["write", "outline", "draft"]):
            return "skills"
        if "handoff" in content:
            return "handoff"
        if re.search(r"\b(plan|coordinate)\b", content):
            return "swarm"
        return "rag"

    def branch(self, state: Dict[str, Any]) -> str:
        return state.get("route", "rag")
