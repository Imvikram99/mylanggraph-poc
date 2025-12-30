"""PEFT / LoRA scaffolding script."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Generate PEFT training stubs.")
console = Console()


@app.command()
def run(
    base_model: str = typer.Option(..., "--base-model"),
    dataset: Path = typer.Option(..., "--dataset", exists=True),
    output_dir: Path = typer.Option(Path("data/peft"), "--output-dir"),
    r: int = typer.Option(8, "--rank", help="LoRA rank"),
    alpha: int = typer.Option(16, "--alpha", help="LoRA alpha"),
):
    output_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "base_model": base_model,
        "dataset": str(dataset),
        "lora_rank": r,
        "lora_alpha": alpha,
        "instructions": "Integrate with HuggingFace PEFT to run actual training.",
    }
    config_path = output_dir / "peft_config.json"
    with config_path.open("w", encoding="utf-8") as fout:
        json.dump(config, fout, indent=2)
    manifest = {
        "adapter": str(config_path),
        "base_model": base_model,
        "dataset": str(dataset),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = output_dir / "adapter_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as fout:
        json.dump(manifest, fout, indent=2)
    console.log(f"[green]PEFT config written[/] {config_path} (manifest={manifest_path})")


if __name__ == "__main__":
    app()
