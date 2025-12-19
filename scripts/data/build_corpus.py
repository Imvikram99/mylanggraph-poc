"""CLI for building cleaned & chunked corpora."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.data_pipeline.builder import build_corpus  # noqa: E402

app = typer.Typer(help="Ingest and chunk documents for training.")
console = Console()


@app.command()
def run(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    dataset_id: str = typer.Option(None, "--dataset-id", "-d", help="Name of the dataset entry."),
    output_root: Path = typer.Option(Path("data/datasets"), "--output-root"),
    manifest: Path = typer.Option(Path("data/datasets/manifest.json"), "--manifest"),
) -> None:
    dataset_id = dataset_id or f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    result = build_corpus(
        input_dir=input_dir,
        dataset_id=dataset_id,
        output_root=output_root,
        manifest_path=manifest,
    )
    console.log(f"[green]Dataset ready[/] id={dataset_id} chunks={result['stats']['chunks']}")


if __name__ == "__main__":
    app()
