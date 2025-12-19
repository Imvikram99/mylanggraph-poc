"""Batch runner for YAML scenarios."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

import typer
import yaml
from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.runner import execute_scenario  # noqa: E402

app = typer.Typer(help="Batch run LangGraph scenarios and assert expectations.")
console = Console()


@app.command()
def run(
    scenarios: List[Path] = typer.Option(
        ...,
        "--scenarios",
        "-s",
        help="Scenario file(s) or directories containing YAML definitions.",
        exists=True,
    ),
    graph_config: Path = typer.Option(
        None,
        "--graph-config",
        help="Optional graph config override.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    files = list(_expand_paths(scenarios))
    if not files:
        raise typer.BadParameter("No scenarios found.")
    failures = 0
    for path in files:
        payload = _load_yaml(path)
        try:
            result = execute_scenario(payload, scenario_name=path.stem, stream=False, graph_config=graph_config)
            _assertions(path, payload.get("assertions", []), result)
            console.log(f"[green]PASS[/] {path}")
        except AssertionError as exc:
            failures += 1
            console.log(f"[red]FAIL[/] {path} -> {exc}")
        except Exception as exc:
            failures += 1
            console.log(f"[red]ERROR[/] {path} -> {exc}")
    if failures:
        raise typer.Exit(code=1)


def _expand_paths(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(path.rglob("*.yaml"))
        elif path.is_file():
            yield path


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fin:
        return yaml.safe_load(fin) or {}


def _assertions(path: Path, assertions: List[Dict[str, Any]], result: Dict[str, Any]) -> None:
    for index, assertion in enumerate(assertions):
        kind = assertion.get("type", "contains")
        if kind == "contains":
            substring = assertion["value"]
            if substring not in str(result.get("output", "")):
                raise AssertionError(f"[{path}] assertion {index} expected '{substring}' in output")
        elif kind == "not_contains":
            substring = assertion["value"]
            if substring in str(result.get("output", "")):
                raise AssertionError(f"[{path}] assertion {index} expected '{substring}' absent from output")
        elif kind == "metadata":
            target = _walk_path(result, assertion.get("path", []))
            if target != assertion.get("equals"):
                raise AssertionError(
                    f"[{path}] assertion {index} expected metadata path {assertion.get('path')} == {assertion.get('equals')} (got {target})"
                )
        else:
            raise AssertionError(f"[{path}] unsupported assertion type '{kind}'")


def _walk_path(payload: Any, path: List[Any]):
    current = payload
    for key in path:
        if isinstance(current, list):
            current = current[key]
        elif isinstance(current, dict):
            current = current[key]
        else:
            raise AssertionError(f"Cannot index into {current}")
    return current


if __name__ == "__main__":
    app()
