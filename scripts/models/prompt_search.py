"""Prompt template exploration utility."""

from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path
from typing import List

import typer
from rich.console import Console

from src.models.prompt_tuning import score_prompt

app = typer.Typer(help="Search prompt templates and score heuristically.")
console = Console()


@app.command()
def run(
    prompt: str = typer.Option(..., "--prompt", help="Prompt template with {topic}."),
    topics: List[str] = typer.Argument(...),
    styles: List[str] = typer.Option(["analytical", "executive"], "--style", help="Tone/style modifiers."),
    output: Path = typer.Option(Path("data/metrics/prompt_search.jsonl"), "--output"),
):
    output.parent.mkdir(parents=True, exist_ok=True)
    best = None
    with output.open("w", encoding="utf-8") as fout:
        for topic, style in product(topics, styles):
            candidate = f"[{style.upper()}] " + prompt.format(topic=topic)
            score = score_prompt(candidate)
            record = {"topic": topic, "style": style, "prompt": candidate, "score": score}
            fout.write(json.dumps(record) + "\n")
            console.log(f"[green]candidate[/] {topic}/{style} score={score}")
            if best is None or score > best["score"]:
                best = record
    if best:
        summary_path = Path("data/metrics/prompt_tuning.json")
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(best, indent=2), encoding="utf-8")
        console.log(f"[cyan]Best prompt[/] {best['style']} topic={best['topic']} score={best['score']}")


if __name__ == "__main__":
    app()
