"""Seed TemporalMemoryStore with curated Phase 1 knowledge."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import shorten
from typing import List, Tuple

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from src.memory.temporal import MemoryRecord, TemporalMemoryStore

KB_ROOT = Path("data/knowledge_base")


def _load_snippet(path: Path, max_chars: int = 400) -> str:
    text = path.read_text(encoding="utf-8").strip()
    normalized = " ".join(text.split())
    return shorten(normalized, width=max_chars, placeholder=" ...")


def _plan_records() -> List[Tuple[Path, str, float]]:
    return [
        (KB_ROOT / "architecture" / "module_responsibilities.md", "architecture", 0.85),
        (KB_ROOT / "workflows" / "routing_playbook.md", "workflow", 0.8),
        (KB_ROOT / "evaluation" / "raft_operational_notes.md", "evaluation", 0.75),
    ]


def main() -> None:
    load_dotenv()
    store = TemporalMemoryStore()
    planned = _plan_records()
    created = 0
    timestamp = datetime.now(timezone.utc)
    for path, category, importance in planned:
        if not path.exists():
            print(f"[skip] Missing knowledge doc: {path}")
            continue
        snippet = _load_snippet(path)
        record = MemoryRecord(
            text=f"{path.name}: {snippet}",
            category=category,
            importance=importance,
            source="phase1_seed",
            timestamp=timestamp,
            metadata={"source_path": str(path)},
        )
        store.write(record)
        created += 1
        print(f"[write] {category} memory from {path}")
    print(f"Seeded {created} memory records.")


if __name__ == "__main__":
    main()
