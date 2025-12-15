"""Research skill tools."""

from __future__ import annotations

from typing import List

from rich.console import Console

console = Console()


def web_search(query: str) -> List[str]:
    """Placeholder web search tool."""
    console.log(f"[bold blue]research_pack.web_search[/] query={query}")
    # In a real implementation this would call Tavily, Bing, etc.
    return [
        f"Result 1 about {query}",
        f"Result 2 discussing {query}",
    ]


def summarize_notes(notes: List[str]) -> str:
    """Condense notes into a single string."""
    if not notes:
        return "No notes to summarize."
    joined = " ".join(notes)
    summary = f"Summary ({len(notes)} items): {joined[:256]}"
    console.log(f"[bold blue]research_pack.summarize_notes[/] summary={summary}")
    return summary
