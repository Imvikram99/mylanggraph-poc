"""Hybrid node that combines RAG + GraphRAG outputs."""

from __future__ import annotations

from typing import Any, Callable, Dict

from rich.console import Console

from ..messages import append_message

console = Console()


class HybridNode:
    """Run RAG and GraphRAG sequentially and merge their outputs."""

    def __init__(
        self,
        rag_runner: Callable[[Dict[str, Any]], Dict[str, Any]],
        graph_runner: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        self.rag_runner = rag_runner
        self.graph_runner = graph_runner

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        state = self.rag_runner(state)
        rag_answer = state.get("output", "")
        state.setdefault("metadata", {})["rag_candidate"] = rag_answer

        state = self.graph_runner(state)
        graph_answer = state.get("output", "")
        state.setdefault("metadata", {})["graph_candidate"] = graph_answer

        merged = self._merge_outputs(rag_answer, graph_answer)
        self._update_messages(state, merged)
        state["output"] = merged
        console.log("[cyan]Hybrid[/] merged RAG + GraphRAG outputs")
        return state

    @staticmethod
    def _merge_outputs(rag_answer: Any, graph_answer: Any) -> str:
        sections = []
        if rag_answer:
            sections.append(f"RAG insight:\n{rag_answer}")
        if graph_answer:
            sections.append(f"Graph insight:\n{graph_answer}")
        if not sections:
            return "No answers were produced by RAG or GraphRAG."
        return "\n\n".join(sections)

    @staticmethod
    def _update_messages(state: Dict[str, Any], merged: str) -> None:
        messages = state.get("messages") or []
        if messages and messages[-1].get("role") == "assistant":
            messages[-1]["content"] = merged
            return
        append_message(state, "assistant", merged)
