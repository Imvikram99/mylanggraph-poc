"""Scan trajectories for adversarial signatures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

import typer
from rich.console import Console

from src.eval.adversarial import AdversarialTester

app = typer.Typer(help="Run adversarial scans across trajectories.")
console = Console()


@app.command()
def scan(
    trajectories: List[Path] = typer.Argument(..., help="Trajectory file(s) or directories.", exists=True),
    report: Path = typer.Option(Path("data/metrics/adversarial_report.json"), "--report"),
) -> None:
    tester = AdversarialTester()
    findings = []
    for path in _expand(trajectories):
        state = json.loads(path.read_text(encoding="utf-8"))
        hits = tester.scan_output(state.get("output", ""))
        if hits:
            findings.append({"trajectory": str(path), "hits": hits})
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    console.log(f"[green]Adversarial scan complete[/] findings={len(findings)} -> {report}")


def _expand(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(path.glob("*.json"))
        else:
            yield path


if __name__ == "__main__":
    app()
