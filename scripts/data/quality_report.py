"""CLI to compute dataset quality metrics."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.data_pipeline.quality import compute_quality_metrics  # noqa: E402

app = typer.Typer(help="Generate quality metrics for datasets.")
console = Console()


@app.command()
def run(
    dataset_file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
    output: Path = typer.Option(Path("data/metrics/data_quality.json"), "--output"),
) -> None:
    metrics = compute_quality_metrics(dataset_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
    else:
        existing = {}
    existing[str(dataset_file)] = metrics
    with output.open("w", encoding="utf-8") as fout:
        json.dump(existing, fout, indent=2)
    console.log(f"[green]Quality metrics saved[/] {output}")


if __name__ == "__main__":
    app()
