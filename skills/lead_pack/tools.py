"""Architecture + stack helper utilities for workflow phases."""

from __future__ import annotations

from typing import List


def choose_stack(feature: str, stack_hint: str = "LangGraph POC") -> str:
    """Recommend how the feature should integrate with the preferred stack."""
    feature = feature.strip() or "the requested feature"
    stack_hint = stack_hint.strip() or "LangGraph POC"
    return (
        f"Favor the {stack_hint} primitives when delivering {feature}: "
        "reuse FeatureState + CostLatencyTracker instead of bespoke globals, "
        "and keep workflow prompt templates in configs/workflows.yaml."
    )


def risk_matrix(feature: str) -> List[str]:
    """Return high-level guardrails the tech lead should echo."""
    feature = feature.strip() or "the requested feature"
    return [
        f"Reviewer gate blocks {feature} unless docs/architecture_plan.md lists the workflow assumptions.",
        f"Telemetry must log router_reason=workflow for {feature} to preserve audit parity.",
        f"Fallback to RAG route if FeatureState serialization regresses after adding {feature}.",
    ]
