"""CLI to prune expired task_state memories."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.memory.temporal import TemporalMemoryStore

app = typer.Typer(help="Maintenance tasks for long-term memory.")
console = Console()


@app.command()
def run() -> None:
    """Remove expired task_state entries from the local store."""
    store = TemporalMemoryStore()
    store.prune()
    console.log("[green]Memory prune complete[/]")


if __name__ == "__main__":
    app()
