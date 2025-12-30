"""Cost and latency tracking for LangGraph runs."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List


class CostLatencyTracker:
    """Instrument node handlers to capture latency + token deltas."""

    def __init__(self, path: Path | str = Path("data/metrics/cost_latency.jsonl")) -> None:
        self.records: List[Dict[str, Any]] = []
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.total_duration = 0.0
        self.total_tokens = 0
        self.cost_usd = 0.0

    def wrap(self, node_name: str, func: Callable[[Dict[str, Any]], Dict[str, Any]]):
        if func is None:
            return None

        def _wrapped(state: Dict[str, Any]):
            before_tokens = self._token_estimate(state)
            start = time.perf_counter()
            result = func(state)
            duration = time.perf_counter() - start
            target = result if isinstance(result, dict) else state
            after_tokens = self._token_estimate(target)
            delta_tokens = max(after_tokens - before_tokens, 0)
            cost = self._cost_estimate(delta_tokens)
            self.total_duration += duration
            self.total_tokens += delta_tokens
            self.cost_usd += cost
            workflow_phase = target.get("workflow_phase") or state.get("workflow_phase") if isinstance(state, dict) else None
            self.records.append(
                {
                    "node": node_name,
                    "duration_s": round(duration, 4),
                    "token_delta": delta_tokens,
                    "cost_usd": round(cost, 6),
                    "workflow_phase": workflow_phase,
                }
            )
            self._update_state_metrics(target, node_name)
            return result

        return _wrapped

    def flush(self, scenario_id: str, route: str | None) -> None:
        if not self.records:
            return
        with self.path.open("a", encoding="utf-8") as fout:
            for record in self.records:
                entry = {
                    **record,
                    "scenario_id": scenario_id,
                    "route": route,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "total_cost_usd": round(self.cost_usd, 6),
                }
                fout.write(json.dumps(entry) + "\n")
        self.records.clear()

    def summary(self) -> Dict[str, Any]:
        return {
            "total_duration_s": round(self.total_duration, 4),
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.cost_usd, 6),
        }

    def _update_state_metrics(self, state: Dict[str, Any], node_name: str) -> None:
        if not isinstance(state, dict):
            return
        metadata = state.setdefault("metadata", {})
        telemetry = metadata.setdefault("telemetry", {})
        telemetry.update(
            {
                "latency_s": round(self.total_duration, 4),
                "cost_estimate_usd": round(self.cost_usd, 6),
                "tokens": self.total_tokens,
                "last_node": node_name,
            }
        )

    def _token_estimate(self, payload: Dict[str, Any]) -> int:
        try:
            serialized = json.dumps(payload, default=str)
        except TypeError:
            serialized = str(payload)
        return max(len(serialized.split()), 1)

    def _cost_estimate(self, tokens: int) -> float:
        return (tokens / 1000) * 0.002
