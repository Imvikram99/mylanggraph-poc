"""Typed state and helper dataclasses for LangGraph nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, TypedDict


class Message(TypedDict, total=False):
    """Minimal chat message representation."""

    role: str
    content: Any
    name: str


class AgentState(TypedDict, total=False):
    """LangGraph agent state contract shared across nodes."""

    messages: List[Message]
    working_memory: Dict[str, Any]
    metadata: Dict[str, Any]
    artifacts: List[Any]
    route: str
    context: Dict[str, Any]
    output: Any
    telemetry: Dict[str, Any]


@dataclass
class RouteDecision:
    """Structured router output persisted to metadata."""

    route: str
    reason: str
    scores: Dict[str, float] = field(default_factory=dict)
