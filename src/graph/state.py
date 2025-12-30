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


class PhasePlan(TypedDict, total=False):
    """Machine-readable phase metadata for planning/execution."""

    name: str
    owners: List[str]
    deliverables: List[str]
    acceptance_tests: List[str]
    owner: str
    acceptance: List[str]


class FeaturePlan(TypedDict, total=False):
    """Structured plan data tracked through workflow phases."""

    request: str
    architecture: Dict[str, Any]
    review: Dict[str, Any]
    implementation: Dict[str, Any]
    metadata: Dict[str, Any]
    review_feedback: List[str]
    phases: List[PhasePlan]


class FeatureState(AgentState, total=False):
    """Extended LangGraph state that stores workflow metadata."""

    plan: FeaturePlan
    checkpoints: List[Dict[str, Any]]
    attempt_counters: Dict[str, int]
    workflow_phase: str


@dataclass
class RouteDecision:
    """Structured router output persisted to metadata."""

    route: str
    reason: str
    scores: Dict[str, float] = field(default_factory=dict)
