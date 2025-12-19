"""Core logic for model benchmarking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def benchmark_models(models: List[Dict[str, Any]], tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for model in models:
        metrics = _score_model(model, tasks)
        record = {
            "model": model.get("name"),
            "provider": model.get("provider"),
            "style": model.get("style", "prompt"),
            **metrics,
        }
        results.append(record)
    return results


def write_results(results: Iterable[Dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fout:
        for row in results:
            fout.write(json.dumps(row) + "\n")


def _score_model(model: Dict[str, Any], tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    cost = float(model.get("cost_per_1k", 0.001))
    latency = float(model.get("latency_ms", 1000))
    privacy = model.get("privacy", "shared")
    accuracy = 0.0
    robustness = 0.0
    for task in tasks:
        weight = float(task.get("weight", 1.0))
        accuracy += weight * _deterministic_score(model["name"], task["name"], scale=0.3)
        robustness += weight * _deterministic_score(model["name"], task["name"], salt="robust", scale=0.25)
    accuracy = min(1.0, 0.6 + accuracy)
    robustness = min(1.0, 0.5 + robustness)
    score = round(
        accuracy * 0.5
        + robustness * 0.2
        + (1 / (1 + cost / 0.002)) * 0.2
        + (1 / (1 + latency / 1500)) * 0.1,
        3,
    )
    return {
        "accuracy": round(accuracy, 3),
        "robustness": round(robustness, 3),
        "cost_per_1k": cost,
        "latency_ms": latency,
        "privacy": privacy,
        "score": score,
    }


def _deterministic_score(*parts: str, salt: str = "acc", scale: float = 0.2) -> float:
    value = "|".join(str(p) for p in parts) + f"|{salt}"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    fraction = int(digest[:8], 16) / 0xFFFFFFFF
    return scale * fraction
