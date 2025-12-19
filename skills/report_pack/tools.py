"""Report/writing tools."""

from __future__ import annotations

from typing import List


def draft_outline(topic: str) -> List[str]:
    """Produce a multi-section outline for the requested topic."""
    topic = topic.strip() or "the requested topic"
    return [
        f"Executive overview of {topic}",
        f"Problem statement and context for {topic}",
        f"Opportunities / risks related to {topic}",
        f"Implementation considerations for {topic}",
        f"Next steps and owner for {topic}",
    ]


def format_report(sections: List[str]) -> str:
    """Return a formatted markdown report from outline sections."""
    lines = []
    for idx, title in enumerate(sections, start=1):
        body = (
            f"Details for **{title}** go here. Summaries can include bullet lists, KPIs, or action items "
            "produced by upstream tools."
        )
        lines.append(f"## {idx}. {title}\n\n{body}")
    return "\n\n".join(lines)
