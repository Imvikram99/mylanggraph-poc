"""Telemetry helpers for LangGraph runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TelemetryLogger:
    """Write streaming events to disk for later analysis."""

    def __init__(self, path: str | Path = "data/metrics/stream.log") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, label: str, payload: Any) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "label": label,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as fout:
            fout.write(json.dumps(entry) + "\n")
