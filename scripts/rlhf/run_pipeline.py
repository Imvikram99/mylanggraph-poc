"""Orchestrate the RLHF / DPO pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.rlhf.pipeline import run_pipeline  # noqa: E402

app = typer.Typer(help="End-to-end RLHF pipeline runner.")
console = Console()


@app.command()
def run(
    preferences: Path = typer.Option(Path("data/annotations/preferences.jsonl"), "--preferences"),
    output_dir: Path = typer.Option(Path("data/rlhf"), "--output-dir"),
) -> None:
    result = run_pipeline(preferences_path=preferences, output_dir=output_dir)
    console.log(f"[green]Pipeline complete[/] reward={result['reward_model']} bias={result['bias']}")


if __name__ == "__main__":
    app()
