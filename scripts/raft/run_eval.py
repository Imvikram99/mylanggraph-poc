"""Placeholder RAFT evaluation runner."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

console = Console()
app = typer.Typer(help="Run RAFT evaluations on saved scenarios.")


@app.command()
def run(
    scenario: Path = typer.Argument(..., exists=True),
    trajectory: Path = typer.Option(None, "--trajectory", help="Existing trajectory file"),
) -> None:
    """Stubbed evaluation logic."""
    console.log("RAFT evaluation (planned) - reporting placeholder metrics.")
    metrics = {
        "faithfulness": 0.0,
        "coverage": 0.0,
        "latency_sec": 0.0,
    }
    if trajectory:
        metrics["trajectory"] = trajectory.name
    console.print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    app()
