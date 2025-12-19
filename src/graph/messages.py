"""Utilities for managing conversation messages."""

from __future__ import annotations

from typing import Any, Dict, List


def append_message(state: Dict[str, Any], role: str, content: Any, *, limit: int = 40, **extra: Any) -> None:
    """Append a message while ensuring the buffer does not exceed the limit."""
    messages = state.setdefault("messages", [])
    payload: Dict[str, Any] = {"role": role, "content": content}
    if extra:
        payload.update(extra)
    messages.append(payload)
    _trim_messages(messages, limit)


def _trim_messages(messages: List[Dict[str, Any]], limit: int) -> None:
    if limit <= 0:
        return
    overflow = len(messages) - limit
    if overflow > 0:
        del messages[:overflow]
