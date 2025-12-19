"""Preference storage and bias metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


PREFERENCES_PATH = Path("data/annotations/preferences.jsonl")


@dataclass
class Preference:
    prompt: str
    response_a: str
    response_b: str
    winner: str
    annotator_id: str
    notes: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "prompt": self.prompt,
            "response_a": self.response_a,
            "response_b": self.response_b,
            "winner": self.winner,
            "annotator_id": self.annotator_id,
            "notes": self.notes,
        }


class PreferenceStore:
    """Append-only preference store with simple bias metrics."""

    def __init__(self, path: Path = PREFERENCES_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, preference: Preference) -> None:
        with self.path.open("a", encoding="utf-8") as fout:
            fout.write(json.dumps(preference.to_dict()) + "\n")

    def list(self) -> List[Dict[str, str]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fin:
            return [json.loads(line) for line in fin if line.strip()]

    def bias_metrics(self) -> Dict[str, float]:
        records = self.list()
        if not records:
            return {"annotators": 0, "dominant_ratio": 0.0}
        counts: Dict[str, int] = {}
        for record in records:
            counts[record.get("annotator_id", "unknown")] = counts.get(record.get("annotator_id", "unknown"), 0) + 1
        dominant = max(counts.values())
        dominant_ratio = dominant / max(len(records), 1)
        return {"annotators": len(counts), "dominant_ratio": dominant_ratio}

    def uncertain_samples(self, top_k: int = 5) -> List[Dict[str, str]]:
        records = self.list()
        uncertain = [
            record
            for record in records
            if record.get("winner") not in {"A", "B"} or record.get("notes", "").lower().startswith("unsure")
        ]
        return uncertain[:top_k]
