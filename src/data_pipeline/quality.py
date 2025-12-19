"""Quality metrics for datasets."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict


def compute_quality_metrics(dataset_file: Path) -> Dict[str, float]:
    lines = [json.loads(line) for line in dataset_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    total = len(lines)
    token_counts = [len(row.get("text", "").split()) for row in lines]
    avg_tokens = sum(token_counts) / total if total else 0.0
    duplicate_ratio = _duplicate_ratio(lines)
    return {
        "chunks": total,
        "avg_tokens_per_chunk": avg_tokens,
        "duplicate_ratio": duplicate_ratio,
    }


def _duplicate_ratio(rows) -> float:
    texts = [row.get("text", "") for row in rows]
    counts = Counter(texts)
    duplicates = sum(count for text, count in counts.items() if count > 1)
    return duplicates / max(len(texts), 1)
