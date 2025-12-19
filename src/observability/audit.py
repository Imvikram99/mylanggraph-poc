"""Run I/O audit logging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..schemas.scenario import IOAuditRecord


class IOAuditLogger:
    def __init__(self, path: Path = Path("data/metrics/io_audit.jsonl")) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: IOAuditRecord) -> None:
        with self.path.open("a", encoding="utf-8") as fout:
            fout.write(record.model_dump_json() + "\n")
