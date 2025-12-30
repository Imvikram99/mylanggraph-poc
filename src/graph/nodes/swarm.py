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
        phases = (state.get("plan") or {}).get("phases") or []
        context = state.get("context", {})
        if phases:
            summary_lines = []
            for idx, phase in enumerate(phases, start=1):
                title = phase.get("name", f"Phase {idx}")
                owners = phase.get("owners") or []
                if not owners and phase.get("owner"):
                    owners = [phase.get("owner")]
                if not owners:
                    owners = [self.planner]
                owner_label = ", ".join(str(owner) for owner in owners if str(owner).strip()) or self.planner
                deliverables = phase.get("deliverables") or []
                acceptance = phase.get("acceptance_tests") or phase.get("acceptance") or []
                summary_lines.append(f"### Phase {idx} – {title} (owner: {owner_label})")
                summary_lines.extend(f"- Deliverable: {item}" for item in deliverables)
                summary_lines.extend(f"- Acceptance: {item}" for item in acceptance)
                summary_lines.append("")
            summary = "\n".join(summary_lines).strip()
        else:
            query = (state.get("messages") or [{}])[-1].get("content", "")
            plan = [f"{self.planner} -> define goals for '{query}'"]
            worker_outputs = [f"{worker} completes task fragment" for worker in self.workers]
            summary = "\n".join(plan + worker_outputs)
        console.log(f"[blue]Swarm[/] planner={self.planner} workers={self.workers} mode={context.get('mode')}")
        state["output"] = summary
        append_message(state, "assistant", summary)
        return state
