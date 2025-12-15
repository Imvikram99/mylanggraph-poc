"""Agent handoff logic."""

from __future__ import annotations

from typing import Any, Dict

from rich.console import Console

console = Console()


class HandoffNode:
    """Simulate delegating workload to another persona."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        current = state.get("metadata", {}).get("agent", "researcher")
        target = self._target_agent(current)
        console.log(f"[yellow]Handoff[/] {current} -> {target}")
        state.setdefault("metadata", {})["agent"] = target
        state.setdefault("messages", []).append({"role": "system", "content": f"Handoff to {target} agent"})
        state["output"] = f"Delegated work to {target}"
        return state

    def _target_agent(self, current: str) -> str:
        agents = self.config.get("agents", {})
        fallback = agents.get(current, {}).get("fallback_agent")
        return fallback or "writer"
