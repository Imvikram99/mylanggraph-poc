"""CLI entry point for running LangGraph scenarios."""

from __future__ import annotations

import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import typer
import yaml
from dotenv import load_dotenv
from pydantic import ValidationError
from rich.console import Console

from .eval import GovernanceLogger
from .graph import build_agent_graph
from .memory import build_checkpointer
from .observability import TelemetryLogger
from .observability.audit import IOAuditLogger
from .observability.costs import CostLatencyTracker
from .schemas import ScenarioInput, ScenarioOutput
from .schemas.scenario import IOAuditRecord

app = typer.Typer(help="Run LangGraph POC scenarios.")
console = Console()
audit_logger = IOAuditLogger()
governance_logger = GovernanceLogger()


@app.command()
def run(
    scenario: Path = typer.Option(
        ...,
        "--scenario",
        "-s",
        help="YAML file describing the prompt/context",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    stream: bool = typer.Option(False, "--stream", help="Stream intermediate events"),
    graph_config: Path = typer.Option(
        None,
        "--graph-config",
        help="Optional graph config override",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Execute a scenario using LangGraph."""
    load_dotenv()
    payload = _load_yaml(scenario)
    try:
        scenario_input = _validate_input(payload, scenario.stem)
    except ValidationError as exc:
        console.log(f"[red]Invalid scenario[/] {scenario}: {exc}")
        raise typer.Exit(code=1) from exc
    console.log(f"Starting graph run ({scenario})")
    result = execute_scenario(scenario_input, scenario.stem, stream=stream, graph_config=graph_config)
    console.rule("Agent response")
    console.print(result.get("output"))
    _save_trajectory(result)


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fin:
        return yaml.safe_load(fin) or {}


def _initial_state(payload: ScenarioInput, scenario_name: str) -> Dict[str, Any]:
    context = dict(payload.context or {})
    scenario_id = context.get("scenario_id") or payload.id or scenario_name
    context.setdefault("scenario_id", scenario_id)
    state = {
        "messages": [{"role": "user", "content": payload.prompt}],
        "context": context,
        "metadata": {"agent": context.get("persona", "researcher")},
    }
    return state


def _invoke_metadata(state: Dict[str, Any], payload: ScenarioInput) -> Dict[str, Any]:
    context = state.get("context", {})
    return {
        "scenario_id": context.get("scenario_id") or payload.id,
        "user_id": context.get("user_id") or "anonymous",
    }


def _build_thread_id(payload: ScenarioInput) -> str:
    context = payload.context or {}
    parts = [
        str(context.get("scenario_id") or payload.id or ""),
        str(context.get("workflow_mode") or ""),
        str(context.get("repo_path") or context.get("repo") or ""),
        str(context.get("target_branch") or context.get("branch") or ""),
        str(payload.prompt or ""),
    ]
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _build_run_config(metadata: Dict[str, Any], thread_id: str) -> Dict[str, Any]:
    return {
        "metadata": metadata,
        "configurable": {"thread_id": thread_id},
    }


def _maybe_resume_state(
    graph,
    run_config: Dict[str, Any],
    state: Dict[str, Any],
    scenario_input: ScenarioInput,
) -> tuple[Dict[str, Any], bool]:
    resume_enabled = os.getenv("WORKFLOW_RESUME", "true").lower() not in {"0", "false", "no"}
    if not resume_enabled:
        return state, False
        
    # Check for forced rerun in context
    force_rerun = (scenario_input.context or {}).get("force_rerun", False)
    if force_rerun:
        console.log("[yellow]Forcing rerun (ignoring checkpoints)[/]")
        return state, False

    if not getattr(graph, "checkpointer", None):
        return state, False
    try:
        snapshot = graph.get_state(run_config)
    except Exception:
        return state, False
    if not snapshot or not snapshot.values:
        return state, False
    context = dict((snapshot.values or {}).get("context") or {})
    context.update(scenario_input.context or {})
    context["resume"] = True
    return {"context": context}, True


def execute_scenario(
    payload: Dict[str, Any] | ScenarioInput,
    scenario_name: str,
    *,
    stream: bool = False,
    graph_config: Path | None = None,
    save_trajectory: bool = False,
):
    load_dotenv()
    scenario_input = payload if isinstance(payload, ScenarioInput) else _validate_input(payload, scenario_name)
    result = _execute_validated_scenario(scenario_input, scenario_name, stream=stream, graph_config=graph_config)
    if save_trajectory:
        _save_trajectory(result)
    return result


def stream_scenario(
    payload: Dict[str, Any] | ScenarioInput,
    scenario_name: str,
    *,
    graph_config: Path | None = None,
):
    load_dotenv()
    scenario_input = payload if isinstance(payload, ScenarioInput) else _validate_input(payload, scenario_name)
    graph, state, run_config, tracker = _prepare_run(scenario_input, scenario_name, graph_config)
    final_state = state
    try:
        for event in graph.stream(state, config=run_config):
            label, payload = _normalize_event(event)
            if isinstance(payload, dict) and "messages" in payload:
                final_state = payload
            yield label, payload
    except Exception as exc:  # pragma: no cover - surface audit info before bubbling up
        _audit_run(scenario_input, None, errors=[str(exc)])
        _finalize_monitor(tracker, scenario_input, None)
        raise
    _audit_run(scenario_input, final_state)
    _finalize_monitor(tracker, scenario_input, final_state)


def _resolve_graph_config(graph_config: Path | None) -> str:
    if graph_config:
        return str(graph_config)
    return os.getenv("GRAPH_CONFIG_PATH", "configs/graph_config.yaml")


def _execute_validated_scenario(
    scenario_input: ScenarioInput,
    scenario_name: str,
    *,
    stream: bool,
    graph_config: Path | None,
):
    graph, state, run_config, tracker = _prepare_run(scenario_input, scenario_name, graph_config)
    try:
        result = _run_graph(graph, state, run_config, stream)
    except Exception as exc:
        _audit_run(scenario_input, None, errors=[str(exc)])
        _finalize_monitor(tracker, scenario_input, None)
        raise
    _audit_run(scenario_input, result)
    _finalize_monitor(tracker, scenario_input, result)
    return result


def _prepare_run(
    scenario_input: ScenarioInput,
    scenario_name: str,
    graph_config: Path | None,
):
    state = _initial_state(scenario_input, scenario_name)
    metadata = _invoke_metadata(state, scenario_input)
    thread_id = _build_thread_id(scenario_input)
    metadata["thread_id"] = thread_id
    run_config = _build_run_config(metadata, thread_id)
    config_path = _resolve_graph_config(graph_config)
    checkpointer = build_checkpointer()
    tracker = CostLatencyTracker()
    graph = build_agent_graph(config_path=config_path, checkpointer=checkpointer, monitor=tracker)
    state, resumed = _maybe_resume_state(graph, run_config, state, scenario_input)
    if resumed:
        metadata["resume"] = True
    return graph, state, run_config, tracker


def _run_graph(graph, state: Dict[str, Any], run_config: Dict[str, Any], stream: bool):
    if stream and hasattr(graph, "stream"):
        return _stream_run(graph, state, run_config)
    return graph.invoke(state, config=run_config)


def _stream_run(graph, state: Dict[str, Any], run_config: Dict[str, Any]):
    logger = TelemetryLogger()
    try:
        final_state = state
        for event in graph.stream(state, config=run_config):
            label, payload = _normalize_event(event)
            logger.log(label, payload)
            console.log(f"[blue]stream[/] {label}: {payload}")
            candidate = _extract_state_from_event(payload)
            if candidate is not None:
                final_state = candidate
        return final_state
    except Exception:  # pragma: no cover - fallback when stream unsupported
        console.log("[yellow]Graph streaming unavailable; falling back to invoke().[/]")
        return graph.invoke(state, config=run_config)


def _normalize_event(event):
    if isinstance(event, tuple) and len(event) == 2:
        return event
    return "event", event


def _extract_state_from_event(payload: Any) -> Dict[str, Any] | None:
    """Handle graph.stream payloads that wrap state dictionaries under node names."""
    if isinstance(payload, dict):
        if "messages" in payload:
            return payload
        if len(payload) == 1:
            inner = next(iter(payload.values()))
            if isinstance(inner, dict) and "messages" in inner:
                return inner
    return None


def _save_trajectory(state: Dict[str, Any]) -> None:
    if os.getenv("SCRUB_TRAJECTORIES", "false").lower() == "true":
        state = {"messages": state.get("messages", []), "output": state.get("output")}
    target_dir = Path(os.getenv("TRAJECTORY_DIR", "data/trajectories"))
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = target_dir / f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    with filename.open("w", encoding="utf-8") as fout:
        json.dump(state, fout, indent=2)
    console.log(f"[green]Trajectory saved[/] {filename}")


def _finalize_monitor(
    tracker: CostLatencyTracker | None,
    scenario_input: ScenarioInput,
    final_state: Dict[str, Any] | None,
) -> None:
    if not tracker:
        return
    scenario_id = scenario_input.context.get("scenario_id") or scenario_input.id or "unknown"
    route = None
    if isinstance(final_state, dict):
        route = final_state.get("route")
    tracker.flush(scenario_id, route)
    if isinstance(final_state, dict):
        governance_logger.log(final_state)


def _validate_input(payload: Dict[str, Any], scenario_name: str) -> ScenarioInput:
    try:
        scenario_input = ScenarioInput.model_validate(payload)
    except ValidationError as exc:
        audit_logger.log(
            IOAuditRecord(
                scenario_id=_scenario_identifier(payload, scenario_name),
                valid_input=False,
                valid_output=False,
                route=None,
                workflow_phase=None,
                errors=[str(exc)],
            )
        )
        raise
    if not scenario_input.id:
        scenario_input = scenario_input.model_copy(update={"id": scenario_name})
    return scenario_input


def _audit_run(scenario_input: ScenarioInput, final_state: Dict[str, Any] | None, errors: List[str] | None = None) -> None:
    error_list = list(errors or [])
    valid_output = False
    route = None
    workflow_phase = _resolve_workflow_phase(final_state)
    if isinstance(final_state, dict):
        try:
            scenario_output = ScenarioOutput.model_validate(
                {
                    "output": final_state.get("output"),
                    "metadata": final_state.get("metadata"),
                    "route": final_state.get("route"),
                }
            )
            valid_output = True
            route = scenario_output.route
        except ValidationError as exc:
            error_list.append(str(exc))
        metadata = final_state.get("metadata") or {}
        evaluations = metadata.get("evaluations")
        if not evaluations:
            valid_output = False
            error_list.append("missing_evaluations")
    record = IOAuditRecord(
        scenario_id=scenario_input.context.get("scenario_id") or scenario_input.id or "unknown",
        valid_input=True,
        valid_output=valid_output,
        route=route,
        workflow_phase=workflow_phase,
        errors=error_list,
    )
    audit_logger.log(record)


def _resolve_workflow_phase(final_state: Dict[str, Any] | None) -> str | None:
    if not isinstance(final_state, dict):
        return None
    phase = final_state.get("workflow_phase")
    if phase in {"execution", "code_review"}:
        return "implementation"
    if phase:
        return phase
    plan = final_state.get("plan") or {}
    if plan.get("phases"):
        return "implementation"
    return None


def _scenario_identifier(payload: Dict[str, Any], scenario_name: str) -> str:
    context = payload.get("context") if isinstance(payload, dict) else None
    return (context or {}).get("scenario_id") or payload.get("id") or scenario_name


if __name__ == "__main__":
    app()
