"""Helper CLI to scaffold feature-request scenarios."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml

app = typer.Typer(help="Scaffold feature-request scenario files.")


@app.command()
def create(
    prompt: str = typer.Option(
        "Architect a new workflow for this feature request.",
        "--prompt",
        "-p",
        help="User prompt to embed in the scenario.",
    ),
    persona: str = typer.Option("architect", "--persona", help="Persona for the scenario context."),
    stack: str = typer.Option("LangGraph POC", "--stack", help="Stack/solution hint."),
    scenario_id: str = typer.Option("feature_request", "--scenario-id", help="Scenario identifier."),
    deadline: Optional[str] = typer.Option(None, "--deadline", help="Optional deadline metadata."),
    output: Path = typer.Option(
        Path("demo/feature_request_generated.yaml"),
        "--output",
        "-o",
        help="Path where the scenario YAML will be written.",
    ),
):
    """Create a scenario YAML with the workflow context pre-populated."""
    context = {
        "persona": persona,
        "mode": "architect",
        "stack": stack,
        "scenario_id": scenario_id,
    }
    if deadline:
        context["deadline"] = deadline
    scenario = {
        "prompt": prompt,
        "context": context,
        "assertions": [
            {"type": "metadata", "path": ["metadata", "router_reason"], "equals": "workflow_request"},
            {"type": "contains", "value": "Tech Lead Plan"},
            {"type": "contains", "value": "Phase 1"},
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fout:
        yaml.safe_dump(scenario, fout, sort_keys=False)
    typer.secho(f"Scenario written to {output}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
