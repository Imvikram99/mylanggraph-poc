"""Corpus building utilities."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List


def build_corpus(
    input_dir: Path,
    dataset_id: str,
    *,
    output_root: Path = Path("data/datasets"),
    manifest_path: Path = Path("data/datasets/manifest.json"),
    chunk_size: int = 600,
) -> Dict[str, any]:
    """Create a cleaned + chunked corpus and update the dataset manifest."""
    docs = _load_documents(input_dir)
    cleaned = [(path, _clean_text(text)) for path, text in docs if text.strip()]
    deduped = _deduplicate(cleaned)
    chunks = _chunk_documents(deduped, chunk_size=chunk_size)
    dataset_dir = output_root / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    output_file = dataset_dir / "chunks.jsonl"
    _write_chunks(chunks, output_file)
    stats = _stats(deduped, chunks)
    manifest_entry = {
        "id": dataset_id,
        "path": str(output_file),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(input_dir),
        "stats": stats,
        "schema": {"fields": ["dataset_id", "chunk_id", "source_path", "text"]},
    }
    _update_manifest(manifest_path, manifest_entry)
    return {"output": str(output_file), "stats": stats}


def _load_documents(root: Path) -> List[tuple[str, str]]:
    data: List[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        data.append((str(path), text))
    return data


def _clean_text(text: str) -> str:
    normalized = " ".join(text.split())
    return normalized.strip()


def _deduplicate(pairs: Iterable[tuple[str, str]]) -> List[tuple[str, str]]:
    seen = set()
    result = []
    for path, text in pairs:
        signature = hash(text)
        if signature in seen:
            continue
        seen.add(signature)
        result.append((path, text))
    return result


def _chunk_documents(pairs: Iterable[tuple[str, str]], chunk_size: int) -> List[Dict[str, str]]:
    chunks: List[Dict[str, str]] = []
    for idx, (path, text) in enumerate(pairs):
        words = text.split()
        for chunk_idx in range(0, len(words), chunk_size):
            segment = " ".join(words[chunk_idx : chunk_idx + chunk_size])
            chunk_id = f"{idx}-{chunk_idx // chunk_size}"
            chunks.append(
                {
                    "dataset_id": os.path.basename(path),
                    "chunk_id": chunk_id,
                    "source_path": path,
                    "text": segment,
                }
            )
    return chunks


def _write_chunks(chunks: List[Dict[str, str]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as fout:
        for row in chunks:
            fout.write(json.dumps(row) + "\n")


def _stats(docs: List[tuple[str, str]], chunks: List[Dict[str, str]]) -> Dict[str, float]:
    total_tokens = sum(len(doc[1].split()) for doc in docs) or 1
    return {
        "documents": len(docs),
        "chunks": len(chunks),
        "avg_tokens_per_doc": total_tokens / max(len(docs), 1),
    }


def _update_manifest(path: Path, entry: Dict[str, any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8") or '{"datasets": []}')
    else:
        data = {"datasets": []}
    datasets = [dataset for dataset in data.get("datasets", []) if dataset.get("id") != entry["id"]]
    datasets.append(entry)
    data["datasets"] = datasets
    with path.open("w", encoding="utf-8") as fout:
        json.dump(data, fout, indent=2)
