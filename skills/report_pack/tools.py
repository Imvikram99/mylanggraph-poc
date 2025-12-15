"""Report/writing tools."""

from __future__ import annotations

from typing import List


def draft_outline(topic: str) -> List[str]:
    """Produce a lightweight outline for the requested topic."""
    return [
        f"Introduction to {topic}",
        f"Key considerations for {topic}",
        f"Conclusion and next steps for {topic}",
    ]


def format_report(sections: List[str]) -> str:
    """Return a formatted markdown report from outline sections."""
    lines = [f"## {idx+1}. {title}" for idx, title in enumerate(sections)]
    return "\n\n".join(lines)
