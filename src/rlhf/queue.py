"""Annotation queue + sampling utilities."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional


QUEUE_PATH = Path("data/annotations/queue.jsonl")


@dataclass
class AnnotationTask:
    prompt: str
    response_a: str
    response_b: str
    priority: int = 0
    status: str = "pending"
    task_id: str = ""

    def to_dict(self) -> Dict[str, str | int]:
        payload = asdict(self)
        if not payload.get("task_id"):
            payload["task_id"] = str(uuid.uuid4())
        return payload


class AnnotationQueue:
    def __init__(self, path: Path = QUEUE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def enqueue(self, task: AnnotationTask) -> Dict[str, str]:
        record = task.to_dict()
        with self.path.open("a", encoding="utf-8") as fout:
            fout.write(json.dumps(record) + "\n")
        return record

    def list(self) -> List[Dict[str, str]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fin:
            return [json.loads(line) for line in fin if line.strip()]

    def next_task(self) -> Optional[Dict[str, str]]:
        tasks = self.list()
        pending = [task for task in tasks if task.get("status") == "pending"]
        if not pending:
            return None
        best = sorted(pending, key=lambda item: item.get("priority", 0), reverse=True)[0]
        self._update_status(best["task_id"], "assigned")
        return best

    def _update_status(self, task_id: str, status: str) -> None:
        tasks = self.list()
        with self.path.open("w", encoding="utf-8") as fout:
            for task in tasks:
                if task.get("task_id") == task_id:
                    task["status"] = status
                fout.write(json.dumps(task) + "\n")

    def complete(self, task_id: str) -> None:
        self._update_status(task_id, "completed")
