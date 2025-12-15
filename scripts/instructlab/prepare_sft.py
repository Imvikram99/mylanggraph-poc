"""Scaffold for exporting trajectories into InstructLab format."""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(help="Prepare SFT dataset from trajectory logs.")


@app.command()
def run(
    source: Path = typer.Argument(Path("data/trajectories"), help="Directory of saved trajectories"),
    output: Path = typer.Option(Path("data/instructlab/dataset.jsonl"), "--output", help="Output dataset file"),
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as fout:
        for file in sorted(source.glob("run_*.json")):
            record = json.loads(file.read_text(encoding="utf-8"))
            sample = {
                "input": record.get("messages", []),
                "output": record.get("output"),
            }
            fout.write(json.dumps(sample) + "\n")
            count += 1
    typer.echo(f"Wrote {count} samples to {output}")


if __name__ == "__main__":
    app()
