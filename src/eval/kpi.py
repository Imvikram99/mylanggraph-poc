"""Connect evaluation outputs to product/business KPIs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import yaml


class KPIReporter:
    def __init__(
        self,
        target_config: Path = Path("configs/kpi_targets.yaml"),
        log_path: Path = Path("data/metrics/kpi_report.jsonl"),
    ) -> None:
        self.targets = self._load_targets(target_config)
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, metrics: Dict[str, float], state: Dict[str, any]) -> Dict[str, float]:
        derived = self._derive_kpis(metrics)
        record = {
            "scenario": state.get("context", {}).get("scenario_id"),
            "route": state.get("route"),
            "kpis": derived,
            "targets": self.targets.get("targets", {}),
        }
        with self.log_path.open("a", encoding="utf-8") as fout:
            fout.write(json.dumps(record) + "\n")
        return derived

    def _derive_kpis(self, metrics: Dict[str, float]) -> Dict[str, float]:
        relevance = metrics.get("relevance", 0.0)
        hallucination = metrics.get("hallucination", 0.0)
        safety = metrics.get("safety", 0.0)
        weights = self.targets.get("weights", {})
        success_rate = (relevance * weights.get("relevance", 0.4)) + (
            (1 - hallucination) * weights.get("hallucination", 0.3)
        )
        csat = 5 * (0.5 * relevance + 0.5 * safety)
        escalation_rate = max(0.0, 1 - safety)
        return {
            "success_rate": round(min(success_rate, 1.0), 3),
            "csat": round(csat, 2),
            "escalation_rate": round(escalation_rate, 3),
        }

    def _load_targets(self, path: Path) -> Dict[str, Dict[str, float]]:
        if not path.exists():
            return {"targets": {}, "weights": {}}
        with path.open("r", encoding="utf-8") as fin:
            return yaml.safe_load(fin) or {"targets": {}, "weights": {}}
