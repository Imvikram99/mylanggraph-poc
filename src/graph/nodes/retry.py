"""Retry wrappers for LangGraph nodes."""

from __future__ import annotations

from typing import Any, Callable, Dict

from tenacity import Retrying, stop_after_attempt, wait_fixed


class RetryNode:
    """Wrap a node callable with retry semantics."""

    def __init__(
        self,
        node_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        *,
        name: str,
        attempts: int = 2,
        wait_seconds: float = 0.5,
    ) -> None:
        self.node_fn = node_fn
        self.name = name
        self.attempts = max(1, attempts)
        self.wait_seconds = max(0.0, wait_seconds)

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        retrying = Retrying(
            stop=stop_after_attempt(self.attempts),
            wait=wait_fixed(self.wait_seconds),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                return self.node_fn(state)
        return state
