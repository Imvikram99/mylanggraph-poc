"""CLI for generating synthetic variants of datasets."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.data_pipeline.augment import augment_dataset  # noqa: E402

app = typer.Typer(help="Create augmented datasets for robustness experiments.")
console = Console()


@app.command()
def run(
    dataset_file: Path = typer.Argument(..., exists=True, dir_okay=False, file_okay=True),
    dataset_id: str = typer.Option(None, "--dataset-id", "-d", help="Name for the augmented dataset."),
    variants: int = typer.Option(2, "--variants", "-v", help="Variants per record."),
    noise_probability: float = typer.Option(0.1, "--noise", help="Chance of injecting noise characters."),
    output_root: Path = typer.Option(Path("data/datasets"), "--output-root"),
    manifest: Path = typer.Option(Path("data/datasets/manifest.json"), "--manifest"),
    seed: int = typer.Option(0, "--seed", help="Random seed for reproducibility."),
) -> None:
    dataset_id = dataset_id or f"augmented_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    result = augment_dataset(
        dataset_file=dataset_file,
        dataset_id=dataset_id,
        output_root=output_root,
        manifest_path=manifest,
        variants_per_record=variants,
        noise_probability=noise_probability,
        seed=seed,
    )
    console.log(
        "[green]Augmented dataset ready[/] "
        f"id={dataset_id} source={dataset_file} records={result['stats']['augmented_records']}"
    )


if __name__ == "__main__":
    app()
