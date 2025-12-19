"""CLI to train reward models from preference data."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.rlhf.preferences import PreferenceStore  # noqa: E402
from src.rlhf.reward import train_reward_model  # noqa: E402
from src.services.experiment_tracker import ExperimentTracker  # noqa: E402

app = typer.Typer(help="Train reward model stubs from preference data.")
console = Console()


@app.command()
def run(
    preferences: Path = typer.Option(Path("data/annotations/preferences.jsonl"), "--preferences", exists=False),
    output: Path = typer.Option(Path("data/rlhf/reward_model.json"), "--output"),
) -> None:
    store = PreferenceStore(preferences)
    prefs = store.list()
    weights = train_reward_model(prefs, output)
    ExperimentTracker().log(
        run_type="reward_training",
        params={"preferences_path": str(preferences), "output_path": str(output)},
        metrics={"weights": weights, "count": len(prefs)},
    )
    console.log(f"[green]Reward model saved[/] {output} weights={weights}")


if __name__ == "__main__":
    app()
