"""Research skill tools."""

from __future__ import annotations

from typing import List

from rich.console import Console

from src.services import VectorStoreRetriever

console = Console()
_retriever = VectorStoreRetriever()


def web_search(query: str) -> List[str]:
    """Search the configured knowledge base or vector store."""
    console.log(f"[bold blue]research_pack.web_search[/] query={query}")
    results = _retriever.search(query, top_k=5)
    if not results:
        return [f"No documents found for '{query}'. Run scripts/ingest.py to populate the store."]
    formatted = []
    for idx, doc in enumerate(results, start=1):
        source = doc.metadata.get("source") or doc.metadata.get("path") or "unknown"
        formatted.append(f"{idx}. {doc.text} (source: {source})")
    return formatted


def summarize_notes(notes: List[str]) -> str:
    """Condense notes into a single string."""
    if not notes:
        return "No notes to summarize."
    unique_notes = list(dict.fromkeys(note.strip() for note in notes if note.strip()))
    joined = " ".join(unique_notes)
    summary = f"Summary ({len(unique_notes)} items): {joined[:512]}"
    console.log(f"[bold blue]research_pack.summarize_notes[/] len={len(unique_notes)}")
    return summary
