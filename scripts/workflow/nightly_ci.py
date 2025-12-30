"""Nightly CI helper to run RLHF pipeline + workflow scenario."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.rlhf.run_pipeline import run_pipeline  # noqa: E402
from src.runner import execute_scenario  # noqa: E402

app = typer.Typer(help="Run RLHF pipeline followed by feature-request scenario for CI.")
console = Console()


@app.command()
def run(
    preferences: Path = typer.Option(Path("data/annotations/preferences.jsonl"), "--preferences"),
    output_dir: Path = typer.Option(Path("data/rlhf"), "--output-dir"),
    scenario: Path = typer.Option(Path("demo/feature_request.yaml"), "--scenario", exists=True),
    graph_config: Path = typer.Option(Path("configs/graph_config.dev.yaml"), "--graph-config", exists=True),
    report: Path = typer.Option(Path("data/metrics/nightly_ci.jsonl"), "--report"),
):
    result = run_pipeline(preferences_path=preferences, output_dir=output_dir)
    payload = json.loads(scenario.read_text(encoding="utf-8"))
    run_result = execute_scenario(payload, scenario_name=scenario.stem, graph_config=graph_config)
    report.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "pipeline": result,
        "scenario": scenario.stem,
        "route": run_result.get("route"),
        "reward_score": (run_result.get("metadata") or {}).get("reward_score"),
    }
    with report.open("a", encoding="utf-8") as fout:
        fout.write(json.dumps(entry) + "\n")
    console.log(f"[green]Nightly CI[/] route={entry['route']} reward={entry['reward_score']}")


if __name__ == "__main__":
    app()
