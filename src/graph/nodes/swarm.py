"""Swarm coordinator node."""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console

from ..messages import append_message

console = Console()


class SwarmNode:
    """Coordinate planner and workers (placeholder)."""

    def __init__(self, config: Dict[str, Any]) -> None:
        swarm_cfg = config.get("swarm", {})
        self.planner = swarm_cfg.get("planner", "researcher")
        self.workers: List[str] = swarm_cfg.get("workers", ["researcher", "writer"])

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        query = (state.get("messages") or [{}])[-1].get("content", "")
        plan = [f"{self.planner} -> define goals for '{query}'"]
        worker_outputs = [f"{worker} completes task fragment" for worker in self.workers]
        summary = "\n".join(plan + worker_outputs)
        console.log(f"[blue]Swarm[/] planner={self.planner} workers={self.workers}")
        state["output"] = summary
        append_message(state, "assistant", summary)
        return state
