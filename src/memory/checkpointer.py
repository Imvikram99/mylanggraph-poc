"""LangGraph checkpointer helpers."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except Exception:  # pragma: no cover - optional dependency
    SqliteSaver = None  # type: ignore

logger = logging.getLogger(__name__)


class TaggedSqliteSaver:
    """Decorator around SqliteSaver that adds tags and state diffs to metadata."""

    def __init__(self, inner) -> None:
        self.inner = inner

    def put(self, config, checkpoint, metadata=None, *args, **kwargs):  # pragma: no cover - thin wrapper
        metadata = self._augment_metadata(config, metadata, checkpoint)
        return self.inner.put(config, checkpoint, metadata, *args, **kwargs)

    def _augment_metadata(self, config: Dict[str, Any], metadata: Optional[Dict[str, Any]], checkpoint: Dict[str, Any]):
        metadata = metadata or {}
        tags = set(metadata.get("tags", []))
        config_meta = (config or {}).get("metadata", {})
        scenario = config_meta.get("scenario_id")
        user_id = config_meta.get("user_id")
        if scenario:
            tags.add(f"scenario:{scenario}")
        if user_id:
            tags.add(f"user:{user_id}")
        metadata["tags"] = sorted(tags)

        state = checkpoint.get("state", {})
        metadata["state_diff"] = sorted(k for k, v in state.items() if v not in (None, [], {}))
        metadata["message_count"] = len(state.get("messages", []))
        return metadata

    def __getattr__(self, item):  # pragma: no cover - delegate methods
        return getattr(self.inner, item)


def build_checkpointer(db_path: Optional[str] = None):
    """Return a SQLite checkpointer stored inside data/memory by default."""
    if SqliteSaver is None:
        logger.warning("LangGraph SQLite saver unavailable; continuing without checkpoint persistence.")
        return None
    path = Path(db_path or "data/memory/checkpointer.sqlite")
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(conn)
    return TaggedSqliteSaver(saver)
