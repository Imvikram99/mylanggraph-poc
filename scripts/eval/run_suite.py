"""Run evaluation suite on saved trajectories."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from src.eval import EvaluationSuite, GovernanceLogger, KPIReporter
from src.eval.judge import LLMJudge

app = typer.Typer(help="Run evaluation + governance checks on trajectories.")
console = Console()


@app.command()
def run(
    trajectory: Path = typer.Argument(..., exists=True, help="Path to trajectory JSON."),
    requirements: str = typer.Option("Ensure factual accuracy.", "--requirements", help="Judge rubric."),
    judge_model: str = typer.Option("gpt-4o-mini", "--judge-model"),
    show_robustness: bool = typer.Option(False, "--show-robustness", help="Print perturbation cases."),
):
    state = json.loads(trajectory.read_text(encoding="utf-8"))
    suite = EvaluationSuite()
    metrics = suite.evaluate(state)
    governance = GovernanceLogger().log(state)
    kpis = KPIReporter().log(metrics, state)
    judge = LLMJudge(model_name=judge_model)
    output = state.get("output", "")
    prompt = state.get("messages", [{}])[0].get("content", "")
    judge_metrics = judge.score(prompt, output, requirements)
    console.log(f"[green]Eval[/] metrics={metrics} governance={governance} kpis={kpis} judge={judge_metrics}")
    if show_robustness:
        console.log(f"[cyan]Robustness cases[/] {suite.robustness_suite.score(output)}")


if __name__ == "__main__":
    app()
