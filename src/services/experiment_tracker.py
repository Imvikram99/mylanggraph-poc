"""Local experiment tracking inspired by MLflow/W&B."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class ExperimentTracker:
    def __init__(self, path: Path | str = Path("data/metrics/experiments.jsonl")) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, *, run_type: str, params: Dict[str, Any], metrics: Dict[str, Any]) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_type": run_type,
            "params": params,
            "metrics": metrics,
        }
        with self.path.open("a", encoding="utf-8") as fout:
            fout.write(json.dumps(record) + "\n")
