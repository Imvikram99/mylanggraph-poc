"""Replay stored trajectories for debugging."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()


@app.command()
def replay(path: Path = typer.Argument(..., exists=True)) -> None:
    """Print the saved trajectory to the console."""
    data = json.loads(path.read_text(encoding="utf-8"))
    table = Table(title=f"Trajectory {path.name}")
    table.add_column("Role")
    table.add_column("Content")
    for message in data.get("messages", []):
        table.add_row(message.get("role", "?"), str(message.get("content", ""))[:120])
    console.print(table)
    console.rule("Output")
    console.print(data.get("output"))


if __name__ == "__main__":
    app()
