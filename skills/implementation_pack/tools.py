"""Implementation planning helpers for workflow phases."""

from __future__ import annotations

from typing import Dict, List


def phase_breakdown(feature: str, phases: List[str] | None = None) -> List[str]:
    """Return human-readable deliverables for each implementation phase."""
    feature = feature.strip() or "the requested feature"
    phases = phases or ["Design Hardening", "Implementation", "Validation"]
    deliverables = []
    for idx, phase in enumerate(phases, start=1):
        deliverables.append(
            f"Phase {idx} – {phase}: ensure {feature} has owners, telemetry, and exit tests documented."
        )
    return deliverables


def dependency_matrix(feature: str) -> Dict[str, str]:
    """Map core dependencies to the reason they block the feature."""
    feature = feature.strip() or "the requested feature"
    return {
        "FeatureState schema": f"Needed so {feature} can store plan/checkpoint metadata.",
        "configs/workflows.yaml": f"Keeps {feature} prompts centralized for Architect/Reviewer/Tech Lead.",
        "demo/feature_request.yaml": f"Proves {feature} route stays deterministic in CI.",
    }
