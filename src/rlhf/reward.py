"""Reward-model training + scoring helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional


def train_reward_model(preferences: List[Dict[str, str]], output_path: Path) -> Dict[str, float]:
    """Mock reward trainer that records simple statistics."""
    wins_a = sum(1 for pref in preferences if pref.get("winner") == "A")
    wins_b = sum(1 for pref in preferences if pref.get("winner") == "B")
    total = max(len(preferences), 1)
    weights = {"w_pref": wins_a / total, "w_alt": wins_b / total}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fout:
        json.dump({"weights": weights, "count": len(preferences)}, fout, indent=2)
    return weights


class RewardScorer:
    """Lightweight reward scorer that uses trained weights."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = Path(model_path) if model_path else None
        self.weights: Dict[str, float] = {}
        if self.model_path:
            self._load()

    def score(self, output: str, model_path: str | Path | None = None) -> float:
        """Return a normalized reward score for the output."""
        if model_path:
            override = Path(model_path)
            if not self.model_path or override != self.model_path:
                self.model_path = override
                self._load()
        if not self.weights:
            return 0.0
        signal = output.lower()
        pref_weight = self.weights.get("w_pref", 0.5)
        alt_weight = self.weights.get("w_alt", 0.5)
        positive = sum(1 for token in ("aligned", "pass", "success", "ship") if token in signal)
        negative = sum(1 for token in ("fail", "risk", "issue", "stall") if token in signal)
        raw = pref_weight * (1 + positive) - alt_weight * (1 + negative)
        return round(max(min(raw, 1.0), -1.0), 3)

    def _load(self) -> None:
        if not self.model_path or not self.model_path.exists():
            self.weights = {}
            return
        try:
            data = json.loads(self.model_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.weights = {}
            return
        self.weights = data.get("weights", {})
