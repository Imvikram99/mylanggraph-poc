"""Synthetic data augmentation helpers."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from .builder import _update_manifest

DEFAULT_SYNONYMS = {
    "improve": ["enhance", "boost", "refine"],
    "increase": ["grow", "amplify", "raise"],
    "decrease": ["reduce", "lower", "cut"],
    "important": ["critical", "vital", "essential"],
    "plan": ["strategy", "roadmap", "approach"],
    "analysis": ["assessment", "review", "evaluation"],
}


def augment_dataset(
    dataset_file: Path,
    dataset_id: str,
    *,
    output_root: Path = Path("data/datasets"),
    manifest_path: Path = Path("data/datasets/manifest.json"),
    variants_per_record: int = 2,
    noise_probability: float = 0.1,
    seed: int | None = None,
) -> Dict[str, any]:
    """Create augmented samples for robustness experiments."""
    random.seed(seed or 0)
    rows = _load_rows(dataset_file)
    augmented = []
    for row in rows:
        for variant_idx in range(variants_per_record):
            augmented.append(
                _augment_record(
                    row,
                    variant_idx=variant_idx,
                    noise_probability=noise_probability,
                )
            )
    dataset_dir = output_root / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    output_path = dataset_dir / "augmented.jsonl"
    _write_rows(augmented, output_path)
    stats = {
        "source_records": len(rows),
        "augmented_records": len(augmented),
        "variants_per_record": variants_per_record,
        "noise_probability": noise_probability,
    }
    manifest_entry = {
        "id": dataset_id,
        "type": "augmentation",
        "path": str(output_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parent_dataset": str(dataset_file),
        "stats": stats,
        "schema": {
            "fields": ["chunk_id", "text", "source_chunk_id", "augmentation"],
            "augmentation": ["synonym_swap", "sentence_shuffle", "noise_injection"],
        },
    }
    _update_manifest(manifest_path, manifest_entry)
    return {"output": str(output_path), "stats": stats}


def _load_rows(path: Path) -> List[Dict[str, any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_rows(rows: Iterable[Dict[str, any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as fout:
        for row in rows:
            fout.write(json.dumps(row) + "\n")


def _augment_record(record: Dict[str, any], *, variant_idx: int, noise_probability: float) -> Dict[str, any]:
    text = record.get("text", "")
    augmented = _synonym_swap(text)
    augmented = _sentence_shuffle(augmented)
    augmented = _inject_noise(augmented, probability=noise_probability)
    return {
        "chunk_id": f"{record.get('chunk_id')}_aug_{variant_idx}",
        "text": augmented,
        "source_chunk_id": record.get("chunk_id"),
        "augmentation": {
            "synonym_swap": True,
            "sentence_shuffle": True,
            "noise_probability": noise_probability,
        },
    }


def _synonym_swap(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        lower = token.lower()
        if lower not in DEFAULT_SYNONYMS:
            return token
        replacement = random.choice(DEFAULT_SYNONYMS[lower])
        return replacement.capitalize() if token[0].isupper() else replacement

    pattern = re.compile(r"\b(" + "|".join(DEFAULT_SYNONYMS.keys()) + r")\b", flags=re.IGNORECASE)
    return pattern.sub(replace, text)


def _sentence_shuffle(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s for s in sentences if s]
    if len(sentences) <= 1:
        return text
    random.shuffle(sentences)
    return " ".join(sentences)


def _inject_noise(text: str, *, probability: float) -> str:
    chars = []
    for ch in text:
        chars.append(ch)
        if random.random() < probability:
            chars.append(random.choice(["#", "*", "~", "?"]))
    return "".join(chars)
