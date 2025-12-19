"""Memory nodes for LangGraph."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from rich.console import Console

from concurrent.futures import ThreadPoolExecutor

from ...memory.temporal import MemoryRecord, TemporalMemoryStore

console = Console()


class MemoryRetrieveNode:
    """Attach long-term memories to the agent state."""

    def __init__(self, store: TemporalMemoryStore) -> None:
        self.store = store

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        query = _last_user_content(state.get("messages", []))
        if not query:
            return state
        memories = self.store.search(query)
        state.setdefault("working_memory", {})["long_term"] = memories
        if memories:
            console.log(f"[green]Retrieved {len(memories)} temporal memories[/]")
        return state


class MemoryWriteNode:
    """Persist the latest agent insight."""

    def __init__(self, store: TemporalMemoryStore) -> None:
        self.store = store
        self.enabled = os.getenv("ALLOW_MEMORY_WRITE", "true").lower() == "true"
        self._executor = ThreadPoolExecutor(max_workers=1)

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return state
        output = state.get("output")
        if not output:
            return state
        record = MemoryRecord(
            text=str(output),
            category=state.get("context", {}).get("category", "general"),
            importance=state.get("context", {}).get("importance", 0.5),
            source=state.get("metadata", {}).get("agent", "agent"),
            timestamp=datetime.now(timezone.utc),
        )
        self._executor.submit(self.store.write, record)
        return state


def _last_user_content(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
