"""Trajectory snapshot + regression diff utilities."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List

import typer
from rich.console import Console

app = typer.Typer(help="Manage trajectory snapshots and detect regressions.")
console = Console()


@app.command()
def snapshot(
    trajectories: List[Path] = typer.Argument(..., help="Trajectory file(s) to snapshot.", exists=True),
    tag: str = typer.Option(None, "--tag", "-t", help="Snapshot tag (defaults to timestamp)."),
    dest_root: Path = typer.Option(Path("data/trajectories/snapshots"), "--dest-root"),
) -> None:
    tag = tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = dest_root / tag
    dest_dir.mkdir(parents=True, exist_ok=True)
    for path in _expand(trajectories):
        shutil.copy(path, dest_dir / path.name)
    console.log(f"[green]Snapshot saved[/] -> {dest_dir}")


@app.command()
def compare(
    baseline: Path = typer.Argument(..., exists=True, help="Snapshot directory"),
    candidate: Path = typer.Argument(..., exists=True, help="Directory with new trajectories"),
    threshold: float = typer.Option(0.85, "--threshold", help="Min similarity to pass"),
    report: Path = typer.Option(Path("data/metrics/regression_report.json"), "--report"),
) -> None:
    baseline_map = _load_map(baseline)
    candidate_map = _load_map(candidate)
    regressions = []
    for name, base_output in baseline_map.items():
        new_output = candidate_map.get(name)
        if not new_output:
            continue
        similarity = SequenceMatcher(None, base_output, new_output).ratio()
        if similarity < threshold:
            regressions.append({"trajectory": name, "similarity": round(similarity, 3)})
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"regressions": regressions}, indent=2), encoding="utf-8")
    status = "PASS" if not regressions else "FAIL"
    console.log(f"[green]{status}[/] regression check -> {report}")
    if regressions:
        raise typer.Exit(code=1)


def _expand(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(path.glob("*.json"))
        else:
            yield path


def _load_map(directory: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    files = directory.glob("*.json")
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        result[path.name] = data.get("output", "")
    return result


if __name__ == "__main__":
    app()
