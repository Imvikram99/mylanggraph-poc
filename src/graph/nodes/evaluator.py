"""Lightweight evaluator node that scores agent outputs."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

from ...rlhf.reward import RewardScorer

console = Console()


class EvaluatorNode:
    """Score outputs for grounding/coverage and persist metrics."""

    def __init__(
        self,
        metrics_path: str = "data/metrics/raft_runs.jsonl",
        threshold: float = 0.55,
        reward_scorer: RewardScorer | None = None,
    ) -> None:
        self.metrics_path = Path(metrics_path)
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self.reward_scorer = reward_scorer or RewardScorer(os.getenv("REWARD_MODEL_PATH"))

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        evaluation = self._evaluate(state)
        metadata = state.setdefault("metadata", {})
        metadata["reward_score"] = evaluation.get("reward_score")
        metadata.setdefault("evaluations", []).append(evaluation)
        if evaluation["score"] < self.threshold:
            metadata["router_feedback"] = "increase_graph_weight"
        self._persist_metrics(evaluation)
        console.log(f"[cyan]Evaluator[/] score={evaluation['score']:.2f}")
        return state

    def _evaluate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        artifacts: List[Any] = state.get("artifacts", [])
        output = str(state.get("output", "") or "")
        plan = state.get("plan") or {}
        phases = plan.get("phases") or []
        metadata = state.get("metadata") or {}
        code_review = metadata.get("code_review") or {}
        reward_model_path = state.get("context", {}).get("reward_model_path")
        reward_score = self.reward_scorer.score(output, reward_model_path)
        grounding = min(1.0, len(artifacts) / 3.0)
        completeness = 1.0 if len(output.split()) > 30 else 0.5
        phase_coverage = self._phase_coverage(phases, output)
        risk_penalty = 1.0 if code_review.get("status") == "changes_requested" else 0.0
        score = round(
            (grounding * 0.3)
            + (completeness * 0.2)
            + (phase_coverage * 0.25)
            + (reward_score * 0.25)
            - (risk_penalty * 0.2),
            3,
        )
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "route": state.get("route"),
            "scenario": state.get("context", {}).get("scenario_id"),
            "grounding": grounding,
            "completeness": completeness,
            "phase_coverage": phase_coverage,
            "review_status": code_review.get("status"),
             "reward_score": reward_score,
            "score": score,
        }

    def _phase_coverage(self, phases: List[Dict[str, Any]], output: str) -> float:
        if not phases:
            return 1.0
        hits = 0
        lowered = output.lower()
        for phase in phases:
            name = str(phase.get("name") or "").lower()
            if name and name in lowered:
                hits += 1
        return round(hits / max(len(phases), 1), 3)

    def _persist_metrics(self, evaluation: Dict[str, Any]) -> None:
        with self.metrics_path.open("a", encoding="utf-8") as fout:
            fout.write(json.dumps(evaluation) + "\n")
