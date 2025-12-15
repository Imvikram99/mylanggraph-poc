"""CLI entry point for running LangGraph scenarios."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console

from .graph import build_agent_graph
from .memory import build_checkpointer

app = typer.Typer(help="Run LangGraph POC scenarios.")
console = Console()


@app.command()
def run(
    scenario: Path = typer.Argument(..., help="YAML file describing the prompt/context"),
    stream: bool = typer.Option(False, "--stream", help="Stream intermediate events"),
) -> None:
    """Execute a scenario using LangGraph."""
    load_dotenv()
    payload = _load_yaml(scenario)
    state = _initial_state(payload)
    checkpointer = build_checkpointer()
    graph = build_agent_graph(checkpointer=checkpointer)
    console.log("Starting graph run", scenario=scenario)
    result = graph.invoke(state)
    console.rule("Agent response")
    console.print(result.get("output"))
    _save_trajectory(result)


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fin:
        return yaml.safe_load(fin) or {}


def _initial_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    prompt = payload.get("prompt", "Hello LangGraph!")
    context = payload.get("context", {})
    state = {
        "messages": [{"role": "user", "content": prompt}],
        "context": context,
        "metadata": {"agent": context.get("persona", "researcher")},
    }
    return state


def _save_trajectory(state: Dict[str, Any]) -> None:
    if os.getenv("SCRUB_TRAJECTORIES", "false").lower() == "true":
        state = {"messages": state.get("messages", []), "output": state.get("output")}
    target_dir = Path(os.getenv("TRAJECTORY_DIR", "data/trajectories"))
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = target_dir / f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    with filename.open("w", encoding="utf-8") as fout:
        json.dump(state, fout, indent=2)
    console.log(f"[green]Trajectory saved[/] {filename}")


if __name__ == "__main__":
    app()
