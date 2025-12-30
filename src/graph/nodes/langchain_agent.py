"""LangChain AgentExecutor node for autonomous workflows."""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console

from pathlib import Path

from skills.codex_pack.tools import request_codex
from skills.ops_pack.tools import (
    prepare_repo,
    resolve_repo_workspace,
    run_repo_command,
    run_sandboxed,
)

try:  # pragma: no cover - optional dependency components
    from langchain.agents import AgentType, Tool, initialize_agent
    from langchain.llms.fake import FakeListLLM
except Exception:  # pragma: no cover
    AgentType = None  # type: ignore
    Tool = None  # type: ignore
    initialize_agent = None  # type: ignore
    FakeListLLM = None  # type: ignore

console = Console()


class LangChainAgentNode:
    """Demonstrate LangChain AgentExecutor embedded inside LangGraph."""

    def __init__(self) -> None:
        self.available = AgentType is not None and FakeListLLM is not None and Tool is not None and initialize_agent
        if self.available:
            self.agent = self._build_agent()
        else:
            self.agent = None

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.get("plan") or {}
        phases = plan.get("phases") or []
        if phases:
            return self._execute_phases(state, phases)
        query = _last_user_content(state.get("messages", []))
        if not query:
            return state
        metadata = state.setdefault("metadata", {})
        if not self.available or self.agent is None:
            console.log("[yellow]LangChain unavailable; returning heuristic plan[/]")
            plan_text = self._fallback_plan(query)
            metadata["langchain_agent"] = {"iterations": len(plan_text)}
            state.setdefault("messages", []).append({"role": "assistant", "content": plan_text})
            state["output"] = plan_text
            return state
        try:
            result = self.agent.run(query)
        except Exception as exc:  # pragma: no cover - defensive guard
            console.log(f"[red]LangChain agent error[/] {exc}")
            result = self._fallback_plan(query)
        metadata["langchain_agent"] = {
            "iterations": len(metadata.setdefault("langchain_agent", {}).get("iterations", [])) or 2,
            "mode": "langchain_agent",
        }
        state.setdefault("messages", []).append({"role": "assistant", "content": result})
        state["output"] = result
        return state

    def _execute_phases(self, state: Dict[str, Any], phases: List[Dict[str, Any]]) -> Dict[str, Any]:
        metadata = state.setdefault("metadata", {})
        phase_outputs = []
        checkpoints = state.setdefault("checkpoints", [])
        repo_workspace, prep_log = self._prepare_repo_workspace(state)
        phase_exec = metadata.setdefault("phase_execution", {})
        if prep_log:
            phase_exec["repo_prep"] = prep_log
        if repo_workspace:
            phase_exec["repo_path"] = str(repo_workspace)
        repo_branch = state.get("context", {}).get("target_branch")
        repo_ref = str(repo_workspace) if repo_workspace else None
        plan_request = (state.get("plan") or {}).get("request", "")
        for idx, phase in enumerate(phases, start=1):
            owner = phase.get("owner", "architect")
            deliverables = phase.get("deliverables") or []
            acceptance = phase.get("acceptance") or []
            sandbox_cmd = f"phase_{idx}_{phase.get('name', 'unknown').replace(' ', '_').lower()}"
            if repo_workspace:
                repo_cmd = run_repo_command(repo_workspace, f"git status -sb || echo '{sandbox_cmd}'")
            else:
                repo_cmd = run_sandboxed(f"echo Executing {sandbox_cmd}")
            codex_result = self._invoke_codex(
                phase_idx=idx,
                phase=phase,
                feature_request=plan_request,
                repo_path=repo_ref,
                branch=repo_branch,
            )
            summary_lines = [
                f"Phase {idx} – {phase.get('name', f'Phase {idx}')}",
                f"Owner: {owner}",
                "Deliverables:",
            ]
            summary_lines.extend(f"  - {item}" for item in deliverables)
            summary_lines.append("Acceptance:")
            summary_lines.extend(f"  - {item}" for item in acceptance)
            if repo_ref:
                summary_lines.append(f"Repo: {repo_ref}{f' (branch {repo_branch})' if repo_branch else ''}")
                summary_lines.append(f"Repo command: {repo_cmd}")
            else:
                summary_lines.append(f"Sandbox: {repo_cmd}")
            summary_lines.append(f"Codex CLI: {codex_result}")
            phase_output = "\n".join(summary_lines)
            phase_outputs.append(phase_output)
            checkpoints.append({"phase": phase.get("name", f"Phase {idx}"), "owner": owner, "status": "executed"})
            phase_exec.setdefault("codex_calls", []).append({"phase": phase.get("name"), "result": codex_result})
        output = "\n\n".join(phase_outputs)
        phase_exec["count"] = len(phases)
        state["workflow_phase"] = "execution"
        state["output"] = output
        state.setdefault("messages", []).append({"role": "assistant", "content": output})
        return state

    def _build_agent(self):
        llm = FakeListLLM(responses=["Plan: gather intelligence", "Plan: synthesize insights"])
        tools = [
            Tool(
                name="DeskResearch",
                func=lambda q: f"Desk research notes about {q}",
                description="Perform lightweight research using cached knowledge.",
            ),
            Tool(
                name="SummarizeNotes",
                func=lambda notes: f"Synthesized summary: {notes[:100]}",
                description="Summarize notes for stakeholders.",
            ),
        ]
        return initialize_agent(
            tools,
            llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=False,
        )

    def _fallback_plan(self, query: str) -> str:
        steps = [
            f"1. Interpret task: {query}",
            "2. Gather relevant documents.",
            "3. Analyze findings and highlight risks.",
            "4. Produce final brief for stakeholders.",
        ]
        return "\n".join(steps)

    def _prepare_repo_workspace(self, state: Dict[str, Any]) -> tuple[Path | None, str | None]:
        context = state.get("context", {}) or {}
        repo_path = context.get("repo_path")
        repo_url = context.get("repo_url")
        branch = context.get("target_branch")
        feature = context.get("feature_request") or (state.get("plan") or {}).get("request")
        if not repo_path and not repo_url:
            return None, None
        prep_log = prepare_repo(repo_path=repo_path, repo_url=repo_url, branch=branch, feature=feature)
        workspace = resolve_repo_workspace(repo_path=repo_path, repo_url=repo_url)
        return workspace, prep_log

    def _invoke_codex(
        self,
        *,
        phase_idx: int,
        phase: Dict[str, Any],
        feature_request: str,
        repo_path: str | None,
        branch: str | None,
    ) -> str:
        instruction = self._format_phase_instruction(phase_idx, phase, feature_request, repo_path, branch)
        try:
            return request_codex(instruction, repo_path=repo_path, branch=branch)
        except Exception as exc:  # pragma: no cover - defensive fallback
            console.log(f"[red]Codex bridge error[/] {exc}")
            return f"[codex] error: {exc}"

    def _format_phase_instruction(
        self,
        idx: int,
        phase: Dict[str, Any],
        feature_request: str,
        repo_path: str | None,
        branch: str | None,
    ) -> str:
        name = phase.get("name") or f"Phase {idx}"
        deliverables = phase.get("deliverables") or []
        acceptance = phase.get("acceptance") or []
        lines = [
            f"Feature request: {feature_request or 'unspecified'}",
            f"Phase: {name}",
            f"Repo: {repo_path or 'unspecified'}",
            f"Branch: {branch or 'current'}",
            "Deliverables:",
        ]
        if deliverables:
            lines.extend(f"- {item}" for item in deliverables)
        else:
            lines.append("- (not specified)")
        lines.append("Acceptance criteria:")
        if acceptance:
            lines.extend(f"- {item}" for item in acceptance)
        else:
            lines.append("- (not specified)")
        lines.append("Please implement this phase, run relevant tests, and ensure outputs align with guardrails.")
        return "\n".join(lines)


def _last_user_content(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
