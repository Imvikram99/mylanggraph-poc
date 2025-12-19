"""CLI to benchmark registered models across tasks."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import typer
import yaml
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.models.benchmarking import benchmark_models, write_results  # noqa: E402
from src.models.registry import load_models_manifest  # noqa: E402

app = typer.Typer(help="Benchmark configured LLMs/SLMs.")
console = Console()


@app.command()
def run(
    tasks: Path = typer.Option(Path("configs/benchmark_tasks.yaml"), exists=True, help="Benchmark task definition."),
    output: Path = typer.Option(Path("data/metrics/model_benchmarks.jsonl"), help="Where to store benchmark rows."),
    models_config: Path = typer.Option(Path("configs/models.yaml"), exists=True, help="Models manifest."),
) -> None:
    models = load_models_manifest(models_config)
    task_defs = _load_tasks(tasks)
    results = benchmark_models(models, task_defs)
    write_results(results, output)
    _print_table(results)
    console.log(f"[green]Saved[/] benchmark rows to {output}")


def _load_tasks(path: Path):
    with path.open("r", encoding="utf-8") as fin:
        data = yaml.safe_load(fin) or {}
    return data.get("tasks", [])


def _print_table(results):
    table = Table(title="Model Benchmarks")
    headers = ["model", "score", "accuracy", "robustness", "cost_per_1k", "latency_ms"]
    for header in headers:
        table.add_column(header)
    for row in results:
        table.add_row(
            str(row["model"]),
            f"{row['score']:.3f}",
            f"{row['accuracy']:.3f}",
            f"{row['robustness']:.3f}",
            f"{row['cost_per_1k']:.4f}",
            f"{row['latency_ms']:.0f}",
        )
    console.print(table)


if __name__ == "__main__":
    app()
