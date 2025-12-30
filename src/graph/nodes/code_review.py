"""Code review node enforcing playbook guardrails."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console

from ..messages import append_message

console = Console()


class CodeReviewNode:
    """Lightweight reviewer that validates phase deliverables/acceptance tests."""

    def __init__(
        self,
        product_playbook: str = "docs/playbooks/product_alignment.md",
        data_playbook: str = "docs/playbooks/data_engineering.md",
    ) -> None:
        self.product_playbook = Path(product_playbook)
        self.data_playbook = Path(data_playbook)
        self.product_text = self._read_text(self.product_playbook)
        self.data_text = self._read_text(self.data_playbook)

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.get("plan") or {}
        phases = plan.get("phases") or []
        issues = self._validate_phases(phases)
        metadata = state.setdefault("metadata", {})
        review_record = {
            "product_guidance": self.product_text[:200],
            "data_guidance": self.data_text[:200],
            "issues": issues,
            "status": "changes_requested" if issues else "approved",
        }
        metadata["code_review"] = review_record
        if issues:
            message = "Code review flagged issues:\n" + "\n".join(f"- {item}" for item in issues)
            append_message(state, "assistant", message, name="code_review")
            console.log("[red]CodeReview[/] changes requested")
            raise ValueError("Code review failed: issues detected")
        append_message(state, "assistant", "Code review approved all phases.", name="code_review")
        state["workflow_phase"] = "code_review"
        state.setdefault("checkpoints", []).append({"phase": "code_review", "status": "approved"})
        console.log("[green]CodeReview[/] approved plan execution")
        return state

    def _validate_phases(self, phases: List[Dict[str, Any]]) -> List[str]:
        issues: List[str] = []
        for idx, phase in enumerate(phases, start=1):
            name = phase.get("name", f"Phase {idx}")
            owners = phase.get("owners") or []
            if not owners and phase.get("owner"):
                owners = [phase.get("owner")]
            owners = [str(owner).strip() for owner in owners if str(owner).strip()]
            if not owners:
                issues.append(f"{name}: missing owners")
            acceptance = phase.get("acceptance_tests") or phase.get("acceptance") or []
            acceptance = [str(item).strip() for item in acceptance if str(item).strip()]
            if not acceptance:
                issues.append(f"{name}: missing acceptance tests")
            elif not any("demo/" in entry or "pytest" in entry.lower() for entry in acceptance):
                issues.append(f"{name}: acceptance tests missing scenario/test references")
            deliverables = phase.get("deliverables") or []
            if not deliverables:
                issues.append(f"{name}: no deliverables listed")
        return issues

    @staticmethod
    def _read_text(path: Path) -> str:
        if not path.exists():
            return f"{path} missing"
        return path.read_text(encoding="utf-8")
