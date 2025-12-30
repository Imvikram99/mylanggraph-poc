"""Helper CLI to scaffold feature-request scenarios and run them end-to-end."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.runner import execute_scenario  # noqa: E402
from skills.ops_pack.tools import prepare_repo  # noqa: E402

app = typer.Typer(help="Scaffold feature-request scenario files or run them directly.")


def _build_scenario(
    prompt: str,
    persona: str,
    stack: str,
    scenario_id: str,
    deadline: Optional[str],
    repo: Optional[Path],
    repo_url: Optional[str],
    repo_branch: Optional[str],
    feature: Optional[str],
    plan_only: bool = False,
) -> dict:
    context = {
        "persona": persona,
        "mode": "architect",
        "stack": stack,
        "scenario_id": scenario_id,
    }
    if deadline:
        context["deadline"] = deadline
    if repo:
        context["repo_path"] = str(repo.expanduser())
    if repo_url:
        context["repo_url"] = repo_url
    if repo_branch:
        context["target_branch"] = repo_branch
    if feature:
        context["feature_request"] = feature
    if plan_only:
        context["plan_only"] = True
    scenario = {
        "prompt": prompt,
        "context": context,
        "assertions": [
            {"type": "metadata", "path": ["metadata", "router_reason"], "equals": "workflow_request"},
            {"type": "contains", "value": "Tech Lead Plan"},
            {"type": "contains", "value": "Phase 1"},
        ],
    }
    return scenario


def _write_scenario(payload: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fout:
        yaml.safe_dump(payload, fout, sort_keys=False)


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
    repo: Optional[Path] = typer.Option(None, "--repo", help="Local repository path to operate on."),
    repo_url: Optional[str] = typer.Option(None, "--repo-url", help="Git URL to clone if the repo is not local."),
    repo_branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Target Git branch."),
    feature: Optional[str] = typer.Option(None, "--feature", "-f", help="Short feature label."),
    output: Path = typer.Option(
        Path("demo/feature_request_generated.yaml"),
        "--output",
        "-o",
        help="Path where the scenario YAML will be written.",
    ),
    plan_only: bool = typer.Option(False, "--plan-only", help="Embed plan-only mode in the scenario."),
):
    """Create a scenario YAML with the workflow context pre-populated."""
    scenario = _build_scenario(
        prompt,
        persona,
        stack,
        scenario_id,
        deadline,
        repo,
        repo_url,
        repo_branch,
        feature,
        plan_only,
    )
    _write_scenario(scenario, output)
    typer.secho(f"Scenario written to {output}", fg=typer.colors.GREEN)


@app.command("run")
def run_feature(
    prompt: str = typer.Option(..., "--prompt", "-p", help="Feature request to execute."),
    persona: str = typer.Option("architect", "--persona", help="Persona for the scenario context."),
    stack: str = typer.Option("LangGraph POC", "--stack", help="Stack/solution hint."),
    scenario_id: str = typer.Option("feature_request", "--scenario-id", help="Scenario identifier."),
    deadline: Optional[str] = typer.Option(None, "--deadline", help="Optional deadline metadata."),
    repo: Optional[Path] = typer.Option(None, "--repo", help="Local repository path to operate on."),
    repo_url: Optional[str] = typer.Option(None, "--repo-url", help="Git URL to clone if the repo is not local."),
    repo_branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Target Git branch."),
    feature: Optional[str] = typer.Option(None, "--feature", "-f", help="Short feature label."),
    graph_config: Path = typer.Option(Path("configs/graph_config.dev.yaml"), "--graph-config", help="Graph config to use."),
    stream: bool = typer.Option(False, "--stream", help="Stream workflow events."),
    save: Optional[Path] = typer.Option(None, "--save", "-o", help="Optional path to save the generated scenario."),
    prep_only: bool = typer.Option(False, "--prep-only", help="Only prepare the repo/branch and exit without running the workflow."),
    plan_only: bool = typer.Option(False, "--plan-only", help="Stop after planning (skip repo execution/Codex phases)."),
):
    """Create and immediately run a feature workflow scenario."""
    scenario = _build_scenario(
        prompt,
        persona,
        stack,
        scenario_id,
        deadline,
        repo,
        repo_url,
        repo_branch,
        feature,
        plan_only,
    )
    if save:
        _write_scenario(scenario, save)
        typer.secho(f"Scenario written to {save}", fg=typer.colors.BLUE)
    if prep_only:
        repo_path_str = str(repo) if repo else None
        prep_log = prepare_repo(
            repo_path=repo_path_str,
            repo_url=repo_url,
            branch=repo_branch,
            feature=feature,
        )
        typer.secho("Prep-only mode enabled. Skipping workflow execution.", fg=typer.colors.YELLOW)
        typer.echo(prep_log or "No repo log generated.")
        raise typer.Exit()
    scenario_name = scenario["context"].get("scenario_id", scenario_id)
    result = execute_scenario(
        scenario,
        scenario_name,
        stream=stream,
        graph_config=graph_config,
        save_trajectory=True,
    )
    typer.secho(f"Route: {result.get('route')}", fg=typer.colors.CYAN)
    typer.secho(f"Output:\n{result.get('output')}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
