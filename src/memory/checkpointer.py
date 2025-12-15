"""LangGraph checkpointer helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from langgraph.checkpoint.sqlite import SqliteSaver


def build_checkpointer(db_path: Optional[str] = None) -> SqliteSaver:
    """Return a SQLite checkpointer stored inside data/memory by default."""
    path = Path(db_path or "data/memory/checkpointer.sqlite")
    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver.from_conn_string(str(path))
