"""Lightweight evaluator node that scores agent outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

console = Console()


class EvaluatorNode:
    """Score outputs for grounding/coverage and persist metrics."""

    def __init__(self, metrics_path: str = "data/metrics/raft_runs.jsonl", threshold: float = 0.55) -> None:
        self.metrics_path = Path(metrics_path)
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        evaluation = self._evaluate(state)
        metadata = state.setdefault("metadata", {})
        metadata.setdefault("evaluations", []).append(evaluation)
        if evaluation["score"] < self.threshold:
            metadata["router_feedback"] = "increase_graph_weight"
        self._persist_metrics(evaluation)
        console.log(f"[cyan]Evaluator[/] score={evaluation['score']:.2f}")
        return state

    def _evaluate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        artifacts: List[Any] = state.get("artifacts", [])
        output = str(state.get("output", "") or "")
        grounding = min(1.0, len(artifacts) / 3.0)
        completeness = 1.0 if len(output.split()) > 30 else 0.5
        score = round((grounding * 0.6) + (completeness * 0.4), 3)
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "route": state.get("route"),
            "scenario": state.get("context", {}).get("scenario_id"),
            "grounding": grounding,
            "completeness": completeness,
            "score": score,
        }

    def _persist_metrics(self, evaluation: Dict[str, Any]) -> None:
        with self.metrics_path.open("a", encoding="utf-8") as fout:
            fout.write(json.dumps(evaluation) + "\n")
