"""Reward-model training placeholder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


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
