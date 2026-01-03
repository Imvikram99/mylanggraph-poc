"""LangChain AgentExecutor node for autonomous workflows."""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console

from pathlib import Path
from uuid import uuid4

from skills.codex_pack.tools import request_codex
from skills.gemini_pack.tools import request_gemini
from skills.ops_pack.tools import (
    prepare_repo,
    resolve_repo_workspace,
    run_repo_command,
    run_sandboxed,
)
from ...memory.temporal import MemoryRecord, TemporalMemoryStore
from ...observability.command_runs import extract_report_commands, load_command_hints, log_report_commands

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

    def __init__(self, workflow_config: Dict[str, Any] | None = None, memory_store: TemporalMemoryStore | None = None) -> None:
        self.role_prompts = self._load_role_prompts(workflow_config)
        self.memory_store = memory_store
        self.available = AgentType is not None and FakeListLLM is not None and Tool is not None and initialize_agent
        if self.available:
            self.agent = self._build_agent()
        else:
            self.agent = None

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.get("plan") or {}
        phases = plan.get("phases") or []
        context = state.get("context") or {}
        plan_only = context.get("plan_only") or plan.get("metadata", {}).get("plan_only")
        if phases:
            if plan_only:
                metadata = state.setdefault("metadata", {})
                phase_exec = metadata.setdefault("phase_execution", {})
                note = "Plan-only mode enabled; skipping execution phases."
                summary = plan.get("summary") or plan.get("request") or "Planning complete"
                summary = f"{summary} (execution skipped)" if plan.get("summary") else summary
                phase_exec["skipped"] = "plan_only"
                phase_exec["reason"] = note
                state.setdefault("messages", []).append({"role": "system", "content": note})
                state["workflow_phase"] = "plan_only"
                state["output"] = summary
                console.log("[yellow]LangChainAgent[/] skipping execution (plan-only mode)")
                return state
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
        phase_statuses = phase_exec.setdefault("phase_statuses", {})
        resume_enabled = bool((state.get("context") or {}).get("resume"))
        if resume_enabled and not phase_statuses:
            phase_statuses.update(self._derive_phase_statuses(phase_exec, checkpoints))
        completed_phases = {
            name for name, status in phase_statuses.items() if status == "completed"
        }
        if resume_enabled and completed_phases:
            console.log(
                "[yellow]Resume enabled; skipping completed phases:[/] "
                + ", ".join(sorted(completed_phases))
            )
        backend_required = self._plan_requires_backend(phases) and repo_workspace is not None
        backend_handoff_ready = bool(phase_exec.get("backend_handoff_ready"))
        if backend_required:
            phase_exec["backend_required"] = True
        if prep_log:
            phase_exec["repo_prep"] = prep_log
        if repo_workspace:
            phase_exec["repo_path"] = str(repo_workspace)
        repo_branch = context.get("target_branch")
        coding_tool = context.get("coding_tool", "codex")
        review_tool, fallback_review_tool = self._resolve_review_tools(context)
        repo_ref = str(repo_workspace) if repo_workspace else None
        plan_request = (state.get("plan") or {}).get("request", "")
        for idx, phase in enumerate(phases, start=1):
            owners = self._phase_owners(phase)
            owner_label = ", ".join(owners) or "architect"
            deliverables = phase.get("deliverables") or []
            acceptance = phase.get("acceptance_tests") or phase.get("acceptance") or []
            phase_name = phase.get("name", f"Phase {idx}")
            is_backend_phase, is_frontend_phase = self._phase_role_flags(owners)
            if is_frontend_phase and backend_required and not backend_handoff_ready:
                summary_lines = [
                    f"Phase {idx} – {phase_name}",
                    f"Owner: {owner_label}",
                    "Status: blocked (backend handoff incomplete)",
                ]
                if repo_ref:
                    summary_lines.append(f"Repo: {repo_ref}{f' (branch {repo_branch})' if repo_branch else ''}")
                phase_output = "\n".join(summary_lines)
                phase_outputs.append(phase_output)
                phase_statuses[phase_name] = "blocked"
                checkpoints.append(
                    {
                        "phase": phase_name,
                        "owners": owners,
                        "status": "blocked",
                        "reason": "backend_handoff_missing",
                    }
                )
                phase_exec.setdefault("blocked", []).append(
                    {"phase": phase_name, "reason": "backend_handoff_missing"}
                )
                continue
            if resume_enabled and phase_name in completed_phases:
                summary_lines = [
                    f"Phase {idx} – {phase_name}",
                    f"Owner: {owner_label}",
                    "Status: skipped (resume)",
                ]
                if repo_ref:
                    summary_lines.append(f"Repo: {repo_ref}{f' (branch {repo_branch})' if repo_branch else ''}")
                phase_outputs.append("\n".join(summary_lines))
                continue
            sandbox_cmd = f"phase_{idx}_{phase.get('name', 'unknown').replace(' ', '_').lower()}"
            if repo_workspace:
                repo_cmd = run_repo_command(repo_workspace, f"git status -sb || echo '{sandbox_cmd}'")
            else:
                repo_cmd = run_sandboxed(f"echo Executing {sandbox_cmd}")
            session = self._ensure_phase_session(phase_exec, phase_name, plan_request or "feature")
            role_prompt = self._resolve_role_prompt(owners or [owner_label])
            self._maybe_init_phase_session(
                phase_exec,
                phase_name,
                session,
                role_prompt,
                repo_path=repo_ref,
                branch=repo_branch,
                coding_tool=coding_tool,
            )
            instruction = self._format_phase_instruction(
                idx,
                phase,
                plan_request,
                repo_ref,
                repo_branch,
            )
            test_policy = str(phase.get("test_policy") or "").strip().lower()
            if repo_ref and test_policy == "debugger":
                hints = load_command_hints(repo_path=repo_ref, phase=phase_name)
                if hints:
                    instruction = (
                        f"{instruction}\n\nKnown build/test fixes from prior runs:\n"
                        + "\n".join(f"- {hint}" for hint in hints)
                    )
            codex_result = self._invoke_coding_tool(
                phase_idx=idx,
                phase=phase,
                feature_request=plan_request,
                repo_path=repo_ref,
                branch=repo_branch,
                session_id=session["id"],
                session_name=session["name"],
                phase_name=phase_name,
                instruction=instruction,
                coding_tool=coding_tool,
            )
            metadata.setdefault("tool_requests", []).append(
                {
                    "phase": phase_name,
                    "session_id": session["id"],
                    "session_name": session["name"],
                    "instruction": instruction,
                    "tool": coding_tool,
                }
            )
            handoff_report = None
            followup_result = None
            if is_backend_phase and repo_workspace:
                report_path = self._backend_report_path(owners)
                required_sections = ["Build", "Tests", "Run", "API Tests"]
                handoff_report = self._report_status(repo_workspace, report_path, required_sections)
                if not handoff_report["ok"]:
                    followup_instruction = self._handoff_followup_instruction(
                        feature_request=plan_request,
                        phase_name=phase_name,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        report_path=report_path,
                        kind="backend",
                    )
                    followup_result = self._invoke_coding_tool(
                        phase_idx=idx,
                        phase=phase,
                        feature_request=plan_request,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        session_id=session["id"],
                        session_name=session["name"],
                        phase_name=f"{phase_name} (handoff)",
                        instruction=followup_instruction,
                        coding_tool=coding_tool,
                    )
                    metadata.setdefault("tool_requests", []).append(
                        {
                            "phase": f"{phase_name} (handoff)",
                            "session_id": session["id"],
                            "session_name": session["name"],
                            "instruction": followup_instruction,
                            "tool": coding_tool,
                        }
                    )
                    phase_exec.setdefault("tool_calls", []).append(
                        {
                            "phase": f"{phase_name} (handoff)",
                            "result": followup_result,
                            "session_id": session["id"],
                            "tool": coding_tool,
                        }
                    )
                    handoff_report = self._report_status(repo_workspace, report_path, required_sections)
                backend_handoff_ready = handoff_report["ok"]
                phase_exec["backend_handoff_ready"] = backend_handoff_ready
                phase_exec.setdefault("handoff_reports", {})[phase_name] = handoff_report
            elif is_frontend_phase and repo_workspace:
                report_path = self._frontend_report_path()
                required_sections = ["Screens", "Buttons", "Flows", "UI Tests"]
                handoff_report = self._report_status(repo_workspace, report_path, required_sections)
                if not handoff_report["ok"]:
                    followup_instruction = self._handoff_followup_instruction(
                        feature_request=plan_request,
                        phase_name=phase_name,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        report_path=report_path,
                        kind="frontend",
                    )
                    followup_result = self._invoke_coding_tool(
                        phase_idx=idx,
                        phase=phase,
                        feature_request=plan_request,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        session_id=session["id"],
                        session_name=session["name"],
                        phase_name=f"{phase_name} (handoff)",
                        instruction=followup_instruction,
                        coding_tool=coding_tool,
                    )
                    metadata.setdefault("tool_requests", []).append(
                        {
                            "phase": f"{phase_name} (handoff)",
                            "session_id": session["id"],
                            "session_name": session["name"],
                            "instruction": followup_instruction,
                            "tool": coding_tool,
                        }
                    )
                    phase_exec.setdefault("tool_calls", []).append(
                        {
                            "phase": f"{phase_name} (handoff)",
                            "result": followup_result,
                            "session_id": session["id"],
                            "tool": coding_tool,
                        }
                    )
                    handoff_report = self._report_status(repo_workspace, report_path, required_sections)
                phase_exec.setdefault("handoff_reports", {})[phase_name] = handoff_report
            report_paths: List[str] = []
            if is_backend_phase:
                report_paths.append(self._backend_report_path(owners))
            elif is_frontend_phase:
                report_paths.append(self._frontend_report_path())
            if repo_workspace and repo_ref and report_paths:
                log_report_commands(
                    repo_workspace=repo_workspace,
                    report_paths=report_paths,
                    repo_path=repo_ref,
                    branch=repo_branch,
                    phase=phase_name,
                    session_id=session["id"],
                    session_name=session["name"],
                )
            report_failures = []
            if repo_workspace and repo_ref and report_paths:
                report_failures = self._report_failures(
                    repo_workspace=repo_workspace,
                    report_paths=report_paths,
                    repo_path=repo_ref,
                    branch=repo_branch,
                    phase=phase_name,
                    session=session,
                )
            phase_success = self._codex_success(codex_result)
            if report_paths:
                phase_success = not report_failures
            gemini_result = None
            gemini_followup_result = None
            if test_policy == "debugger" and not phase_success:
                original_failures = report_failures
                gemini_attempts = phase_exec.setdefault("gemini_attempts", {})
                if gemini_attempts.get(phase_name, 0) < 1:
                    gemini_attempts[phase_name] = gemini_attempts.get(phase_name, 0) + 1
                    suggestion_file = "docs/gemini_debug_suggestions.md"
                    gemini_session = self._ensure_gemini_session(phase_exec, phase_name, plan_request or "feature")
                    gemini_instruction = self._gemini_debug_instruction(
                        feature_request=plan_request,
                        phase_name=phase_name,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        codex_result=codex_result,
                        followup_result=followup_result,
                        failures=report_failures,
                        suggestion_file=suggestion_file,
                    )
                    gemini_result = request_gemini(
                        gemini_instruction,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        session_id=gemini_session["id"],
                        session_name=gemini_session["name"],
                        phase=phase_name,
                    )
                    metadata.setdefault("gemini_requests", []).append(
                        {
                            "phase": phase_name,
                            "session_id": gemini_session["id"],
                            "session_name": gemini_session["name"],
                            "instruction": gemini_instruction,
                        }
                    )
                    phase_exec.setdefault("gemini_calls", []).append(
                        {
                            "phase": phase_name,
                            "result": gemini_result,
                            "session_id": gemini_session["id"],
                        }
                    )
                    followup_instruction = self._gemini_followup_instruction(
                        feature_request=plan_request,
                        phase_name=phase_name,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        suggestion_file=suggestion_file,
                        report_paths=report_paths,
                    )
                    gemini_followup_result = self._invoke_coding_tool(
                        phase_idx=idx,
                        phase=phase,
                        feature_request=plan_request,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        session_id=session["id"],
                        session_name=session["name"],
                        phase_name=f"{phase_name} (gemini follow-up)",
                        instruction=followup_instruction,
                        coding_tool=coding_tool,
                    )
                    metadata.setdefault("tool_requests", []).append(
                        {
                            "phase": f"{phase_name} (gemini follow-up)",
                            "session_id": session["id"],
                            "session_name": session["name"],
                            "instruction": followup_instruction,
                            "tool": coding_tool,
                        }
                    )
                    phase_exec.setdefault("tool_calls", []).append(
                        {
                            "phase": f"{phase_name} (gemini follow-up)",
                            "result": gemini_followup_result,
                            "session_id": session["id"],
                            "tool": coding_tool,
                        }
                    )
                    if repo_workspace and repo_ref and report_paths:
                        log_report_commands(
                            repo_workspace=repo_workspace,
                            report_paths=report_paths,
                            repo_path=repo_ref,
                            branch=repo_branch,
                            phase=f"{phase_name} (gemini follow-up)",
                            session_id=session["id"],
                            session_name=session["name"],
                        )
                        report_failures = self._report_failures(
                            repo_workspace=repo_workspace,
                            report_paths=report_paths,
                            repo_path=repo_ref,
                            branch=repo_branch,
                            phase=phase_name,
                            session=session,
                        )
                    phase_success = self._codex_success(gemini_followup_result)
                    if report_paths:
                        phase_success = not report_failures
                    if phase_success and self.memory_store:
                        fix_summary = gemini_followup_result or followup_result or codex_result or ""
                        lesson = self._distill_lesson(
                            phase_name,
                            original_failures,
                            fix_summary,
                            review_tool=review_tool,
                            fallback_review_tool=fallback_review_tool,
                            repo_path=repo_ref,
                            branch=repo_branch,
                        )
                        if lesson:
                            self.memory_store.write(
                                MemoryRecord(
                                    text=lesson,
                                    category="golden_rule",
                                    importance=1.0,
                                    metadata={
                                        "phase": phase_name,
                                        "repo": repo_ref,
                                        "review_tool": review_tool,
                                        "fallback_review_tool": fallback_review_tool,
                                    },
                                )
                            )
                            console.log(f"[green]Scribe learned[/] {lesson}")
            phase_statuses[phase_name] = "completed" if phase_success else "failed"
            summary_lines = [
                f"Phase {idx} – {phase_name}",
                f"Owner: {owner_label}",
                f"Codex session: {session['id']}",
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
            summary_lines.append(f"Codex CLI ({coding_tool}): {codex_result}")
            if handoff_report:
                summary_lines.append(
                    f"Handoff report: {handoff_report['path']} ({handoff_report['status']})"
                )
                missing = handoff_report.get("missing_sections")
                if missing:
                    summary_lines.append(f"Handoff report missing: {', '.join(missing)}")
            if followup_result:
                summary_lines.append(f"Codex CLI ({coding_tool} handoff follow-up): {followup_result}")
            if gemini_result:
                summary_lines.append(f"Gemini CLI: {gemini_result}")
            if gemini_followup_result:
                summary_lines.append(f"Codex CLI ({coding_tool} gemini follow-up): {gemini_followup_result}")
            phase_output = "\n".join(summary_lines)
            phase_outputs.append(phase_output)
            checkpoints.append(
                {
                    "phase": phase_name,
                    "owners": owners,
                    "status": "completed" if phase_success else "failed",
                }
            )
            phase_exec.setdefault("tool_calls", []).append(
                {
                    "phase": phase_name,
                    "result": codex_result,
                    "session_id": session["id"],
                    "tool": coding_tool,
                }
            )
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

    @staticmethod
    def _normalize_review_tool(value: Any, default: str) -> str:
        tool = str(value or default).strip().lower()
        if tool in {"", "none", "off", "false"}:
            return ""
        if tool not in {"gemini", "codex", "local"}:
            return default
        return tool

    @classmethod
    def _resolve_review_tools(cls, context: Dict[str, Any]) -> tuple[str, str]:
        review_tool = cls._normalize_review_tool(context.get("review_tool"), "gemini")
        fallback_tool = cls._normalize_review_tool(context.get("fallback_review_tool"), "codex")
        if fallback_tool == review_tool:
            fallback_tool = ""
        return review_tool, fallback_tool

    @staticmethod
    def _review_result_ok(result: str | None) -> bool:
        if not result:
            return False
        lowered = result.lower()
        if "exit=" in lowered:
            return "exit=0" in lowered and "timed out" not in lowered and "error" not in lowered
        return True

    @staticmethod
    def _extract_golden_rule(text: str) -> str:
        marker = "Golden Rule:"
        idx = text.find(marker)
        if idx == -1:
            return ""
        snippet = text[idx:].strip()
        return snippet.splitlines()[0].strip()

    @staticmethod
    def _local_golden_rule(failures: List[Dict[str, Any]], fix: str) -> str:
        if failures:
            entry = failures[0]
            section = entry.get("section") or "workflow"
            command = entry.get("command") or ""
            if command:
                return f"Golden Rule: Always re-run `{command}` and document the exact failure output in the {section} report."
        if fix:
            return "Golden Rule: Re-run the failing command after each fix and record the exact outcome in the test report."
        return ""

    def _invoke_review_tool(
        self,
        *,
        tool: str,
        prompt: str,
        repo_path: str | None,
        branch: str | None,
        phase_name: str,
    ) -> str:
        if tool == "gemini":
            return request_gemini(prompt, repo_path=repo_path, branch=branch, phase=phase_name)
        if tool == "codex":
            return request_codex(prompt, repo_path=repo_path, branch=branch, phase=phase_name)
        return ""

    def _distill_lesson(
        self,
        phase_name: str,
        failures: List[Dict[str, Any]],
        fix: str,
        *,
        review_tool: str,
        fallback_review_tool: str,
        repo_path: str | None,
        branch: str | None,
    ) -> str:
        """Turn a noisy debugging session into a concise lesson."""
        if not self.memory_store:
            return ""
        error_log = self._format_failure_summary(failures)
        fallback_rule = self._local_golden_rule(failures, fix)
        prompt = (
            "Analyze this debugging session.\n"
            f"Context: {phase_name}\n"
            f"Error Log: {error_log[:2000]}\n"
            f"Successful Fix: {fix[:2000]}\n\n"
            "Extract a single, standalone 'Golden Rule' for future agents working on this codebase.\n"
            "The rule must be under 30 words, actionable, and specific.\n"
            "Format: 'Golden Rule: <rule>'\n"
            "Example: 'Golden Rule: Always run npm run build:css before starting the server.'"
        )
        for tool in [review_tool, fallback_review_tool]:
            if not tool:
                continue
            try:
                result = self._invoke_review_tool(
                    tool=tool,
                    prompt=prompt,
                    repo_path=repo_path,
                    branch=branch,
                    phase_name=phase_name,
                )
            except Exception as exc:
                console.log(f"[red]Scribe failed ({tool})[/] {exc}")
                continue
            if self._review_result_ok(result):
                rule = self._extract_golden_rule(result)
                if rule:
                    return rule
        return fallback_rule

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

    def _invoke_coding_tool(
        self,
        *,
        phase_idx: int,
        phase: Dict[str, Any],
        feature_request: str,
        repo_path: str | None,
        branch: str | None,
        session_id: str | None,
        session_name: str | None,
        phase_name: str | None,
        instruction: str | None = None,
        coding_tool: str = "codex",
    ) -> str:
        instruction = instruction or self._format_phase_instruction(
            phase_idx,
            phase,
            feature_request,
            repo_path,
            branch,
        )
        try:
            if coding_tool == "gemini":
                return request_gemini(
                    instruction,
                    repo_path=repo_path,
                    branch=branch,
                    session_id=session_id,
                    session_name=session_name,
                    phase=phase_name,
                )
            return request_codex(
                instruction,
                repo_path=repo_path,
                branch=branch,
                session_id=session_id,
                session_name=session_name,
                phase=phase_name,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            console.log(f"[red]Coding tool error ({coding_tool})[/] {exc}")
            return f"[{coding_tool}] error: {exc}"

    def _format_phase_instruction(
        self,
        idx: int,
        phase: Dict[str, Any],
        feature_request: str,
        repo_path: str | None,
        branch: str | None,
    ) -> str:
        name = phase.get("name") or f"Phase {idx}"
        owners = self._phase_owners(phase)
        test_policy = str(phase.get("test_policy") or "").strip().lower()
        debug_steps = phase.get("debug_steps") or []
        checkpoint_file = phase.get("checkpoint_file")
        handoff_reports = phase.get("handoff_reports") or []
        is_backend_phase, is_frontend_phase = self._phase_role_flags(owners)
        report_path = None
        if is_backend_phase:
            report_path = self._backend_report_path(owners)
        elif is_frontend_phase:
            report_path = self._frontend_report_path()
        deliverables = phase.get("deliverables") or []
        acceptance = phase.get("acceptance_tests") or phase.get("acceptance") or []
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
        if test_policy == "debugger" and checkpoint_file:
            lines.append(f"Checkpoint file: {checkpoint_file} (read if it exists, update after each step).")
        if debug_steps:
            lines.append("Debugger steps:")
            lines.extend(f"- {step}" for step in debug_steps)
        if is_backend_phase and report_path:
            if test_policy == "defer":
                lines.extend(
                    [
                        "Backend handoff requirements (tests deferred):",
                        f"- Record Build, Tests, Run, and API Tests sections in {report_path}.",
                        "- Do not run the commands yet; mark them as deferred.",
                    ]
                )
            else:
                lines.extend(
                    [
                        "Backend handoff requirements:",
                        f"- Record Build, Tests, Run, and API Tests sections in {report_path}.",
                        "- Include exact commands, outcomes, and any failures/waivers.",
                    ]
                )
        if is_frontend_phase and report_path:
            if test_policy == "defer":
                lines.extend(
                    [
                        "Frontend handoff requirements (tests deferred):",
                        f"- Record Screens, Buttons, Flows, and UI Tests sections in {report_path}.",
                        "- Do not run the commands yet; mark them as deferred.",
                    ]
                )
            else:
                lines.extend(
                    [
                        "Frontend handoff requirements:",
                        f"- Record Screens, Buttons, Flows, and UI Tests sections in {report_path}.",
                        "- Include exact commands, outcomes, and any failures/waivers.",
                    ]
                )
        if handoff_reports:
            lines.append("Debugger report updates:")
            lines.extend(f"- Update {path} with actual commands and results." for path in handoff_reports)
        if test_policy == "defer":
            lines.append(
                "Implement code only. Skip full builds/tests; run quick sanity checks if fast."
            )
        elif test_policy == "debugger":
            lines.append(
                "Run the debugger steps, fix failures, and update the checkpoint on time limits."
            )
        else:
            lines.append(
                "Please implement this phase, run relevant tests, and ensure outputs align with guardrails."
            )
        if self.memory_store and repo_path:
            query = f"golden rule {phase.get('name', '')} {repo_path}"
            lessons = self.memory_store.search(query, top_k=3)
            golden_rules = [
                item["text"]
                for item in lessons
                if item.get("category") == "golden_rule" and item.get("score", 0) > 0.5
            ]
            if golden_rules:
                lines.append("\nPROJECT HANDBOOK (CRITICAL):")
                lines.extend(f"- {rule}" for rule in golden_rules)
        return "\n".join(lines)

    @staticmethod
    def _phase_owners(phase: Dict[str, Any]) -> List[str]:
        owners = phase.get("owners") or []
        if not owners and phase.get("owner"):
            owners = [phase.get("owner")]
        return [str(owner) for owner in owners if str(owner).strip()]

    def _phase_role_flags(self, owners: List[str]) -> tuple[bool, bool]:
        normalized = {self._normalize_role(owner) for owner in owners}
        backend_roles = {"lead_java", "lead_python", "backend_lead", "backend"}
        frontend_roles = {"lead_react", "frontend_tech_lead", "lead_frontend", "frontend"}
        is_backend = bool(normalized & backend_roles)
        is_frontend = bool(normalized & frontend_roles)
        return is_backend, is_frontend

    def _plan_requires_backend(self, phases: List[Dict[str, Any]]) -> bool:
        for phase in phases:
            owners = self._phase_owners(phase)
            if self._phase_role_flags(owners)[0]:
                return True
        return False

    def _backend_report_path(self, owners: List[str]) -> str:
        normalized = {self._normalize_role(owner) for owner in owners}
        if "lead_java" in normalized:
            return "docs/backend_test_report_java.md"
        if "lead_python" in normalized:
            return "docs/backend_test_report_python.md"
        return "docs/backend_test_report.md"

    @staticmethod
    def _frontend_report_path() -> str:
        return "docs/frontend_test_report.md"

    @staticmethod
    def _codex_success(result: str | None) -> bool:
        if not result:
            return False
        lowered = result.lower()
        if "exit=0" in lowered and "timed out" not in lowered and "error" not in lowered:
            return True
        return False

    @classmethod
    def _derive_phase_statuses(
        cls,
        phase_exec: Dict[str, Any],
        checkpoints: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        statuses: Dict[str, str] = {}
        for checkpoint in checkpoints:
            phase = checkpoint.get("phase")
            status = checkpoint.get("status")
            if not phase or not status:
                continue
            normalized = "completed" if status == "executed" else str(status)
            statuses[phase] = normalized
        for call in phase_exec.get("tool_calls", []):
            phase = call.get("phase")
            if not phase or phase in statuses:
                continue
            result = call.get("result")
            statuses[phase] = "completed" if cls._codex_success(result) else "failed"
        return statuses

    @staticmethod
    def _report_status(
        repo_workspace: Path | None,
        report_path: str,
        required_sections: List[str],
    ) -> Dict[str, Any]:
        status = {"ok": False, "status": "missing", "path": report_path}
        if not repo_workspace:
            status["status"] = "no_repo"
            return status
        full_path = repo_workspace / report_path
        if not full_path.exists():
            return status
        text = full_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            status["status"] = "empty"
            return status
        lowered = text.lower()
        missing = [section for section in required_sections if section.lower() not in lowered]
        if missing:
            status["status"] = "missing_sections"
            status["missing_sections"] = missing
            return status
        status["ok"] = True
        status["status"] = "ok"
        return status

    def _handoff_followup_instruction(
        self,
        *,
        feature_request: str,
        phase_name: str,
        repo_path: str | None,
        branch: str | None,
        report_path: str,
        kind: str,
    ) -> str:
        focus = "backend" if kind == "backend" else "frontend"
        sections = (
            "Build, Tests, Run, API Tests" if kind == "backend" else "Screens, Buttons, Flows, UI Tests"
        )
        lines = [
            f"Feature request: {feature_request or 'unspecified'}",
            f"Phase: {phase_name} ({focus} handoff follow-up)",
            f"Repo: {repo_path or 'unspecified'}",
            f"Branch: {branch or 'current'}",
            "Task:",
            f"- Update {report_path} with sections for {sections}.",
            "- Include exact commands and results.",
            f"- Only edit {report_path}.",
        ]
        return "\n".join(lines)

    def _resolve_role_prompt(self, owners: List[str]) -> str | None:
        for owner in owners:
            role_key = self._normalize_role(str(owner))
            prompt = self.role_prompts.get(role_key)
            if prompt:
                return prompt
        return None

    def _maybe_init_phase_session(
        self,
        phase_exec: Dict[str, Any],
        phase_name: str,
        session: Dict[str, str],
        role_prompt: str | None,
        *,
        repo_path: str | None,
        branch: str | None,
        coding_tool: str = "codex",
    ) -> None:
        role_prompt = (role_prompt or "").strip()
        if not role_prompt:
            return
        session_inits = phase_exec.setdefault("session_inits", {})
        if phase_name in session_inits:
            return
        init_payload = "\n".join(
            [
                "Session init.",
                f"Role prompt: {role_prompt}",
                "Reply with a short acknowledgement. Await the next task.",
            ]
        )
        # We pass minimal dummy args for phase_idx/phase as they aren't used for simple session init
        result = self._invoke_coding_tool(
            phase_idx=0,
            phase={},
            feature_request="",
            repo_path=repo_path,
            branch=branch,
            session_id=session["id"],
            session_name=session["name"],
            phase_name=phase_name,
            instruction=init_payload,
            coding_tool=coding_tool,
        )
        session_inits[phase_name] = {"session_id": session["id"], "result": result}

    @staticmethod
    def _ensure_phase_session(phase_exec: Dict[str, Any], phase_name: str, feature_request: str) -> Dict[str, str]:
        sessions = phase_exec.setdefault("sessions", {})
        session = sessions.get(phase_name)
        if session:
            return session
        session_id = uuid4().hex
        session_name = f"{feature_request}:{phase_name}"
        session = {"id": session_id, "name": session_name}
        sessions[phase_name] = session
        return session

    @staticmethod
    def _ensure_gemini_session(phase_exec: Dict[str, Any], phase_name: str, feature_request: str) -> Dict[str, str]:
        sessions = phase_exec.setdefault("gemini_sessions", {})
        session = sessions.get(phase_name)
        if session:
            return session
        session_id = uuid4().hex
        session_name = f"{feature_request}:{phase_name}:gemini"
        session = {"id": session_id, "name": session_name}
        sessions[phase_name] = session
        return session

    @staticmethod
    def _normalize_role(value: str) -> str:
        return value.strip().lower().replace(" ", "_").replace("-", "_")

    @staticmethod
    def _report_failures(
        *,
        repo_workspace: Path,
        report_paths: List[str],
        repo_path: str,
        branch: str | None,
        phase: str,
        session: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        failures: List[Dict[str, Any]] = []
        for report_path in report_paths:
            full_path = repo_workspace / report_path
            if not full_path.exists():
                continue
            text = full_path.read_text(encoding="utf-8", errors="ignore")
            entries = extract_report_commands(
                text,
                report_path=report_path,
                repo_path=repo_path,
                branch=branch,
                phase=phase,
                session_id=session.get("id"),
                session_name=session.get("name"),
            )
            failures.extend([entry for entry in entries if entry.get("status") == "failed"])
        return failures

    @staticmethod
    def _format_failure_summary(failures: List[Dict[str, Any]]) -> str:
        if not failures:
            return "- (no failures captured)"
        lines: List[str] = []
        for entry in failures[:3]:
            section = entry.get("section") or "unknown"
            command = entry.get("command") or ""
            workdir = entry.get("workdir") or "."
            signature = entry.get("error_signature") or ""
            result_excerpt = entry.get("result_excerpt") or ""
            lines.append(f"- {section}: `{command}` (workdir: {workdir})")
            if signature:
                lines.append(f"  error: {signature}")
            if result_excerpt:
                lines.append(f"  result: {result_excerpt[:200]}")
        if len(failures) > 3:
            lines.append(f"- ({len(failures) - 3} more failures omitted)")
        return "\n".join(lines)

    def _gemini_debug_instruction(
        self,
        *,
        feature_request: str,
        phase_name: str,
        repo_path: str | None,
        branch: str | None,
        codex_result: str | None,
        followup_result: str | None,
        failures: List[Dict[str, Any]],
        suggestion_file: str,
    ) -> str:
        summary = self._format_failure_summary(failures)
        lines = [
            "You are a debugging advisor. Provide suggestions only; do NOT implement changes.",
            f"Feature request: {feature_request or 'unspecified'}",
            f"Phase: {phase_name}",
            f"Repo: {repo_path or 'unspecified'}",
            f"Branch: {branch or 'current'}",
            "Codex observations:",
            f"- Codex result: {codex_result or 'n/a'}",
        ]
        if followup_result:
            lines.append(f"- Codex handoff follow-up: {followup_result}")
        lines.extend(
            [
                "Observed failures from test reports:",
                summary,
                f"Write a short suggestion list to {suggestion_file}.",
                "Only edit that file; do not modify code or tests.",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _gemini_followup_instruction(
        *,
        feature_request: str,
        phase_name: str,
        repo_path: str | None,
        branch: str | None,
        suggestion_file: str,
        report_paths: List[str],
    ) -> str:
        report_list = ", ".join(report_paths) if report_paths else "test reports"
        lines = [
            f"Feature request: {feature_request or 'unspecified'}",
            f"Phase: {phase_name} (gemini follow-up)",
            f"Repo: {repo_path or 'unspecified'}",
            f"Branch: {branch or 'current'}",
            "Task:",
            f"- Read {suggestion_file}.",
            "- Apply relevant suggestions to fix the failures.",
            "- Re-run the failing commands from the reports.",
            f"- Update {report_list} and docs/debug_state.md with results.",
        ]
        return "\n".join(lines)

    def _load_role_prompts(self, workflow_config: Dict[str, Any] | None) -> Dict[str, str]:
        prompts: Dict[str, str] = {}
        if not workflow_config:
            return prompts
        for key, role in (workflow_config.get("roles") or {}).items():
            prompt = (role or {}).get("prompt")
            if prompt:
                prompts[self._normalize_role(str(key))] = str(prompt)
        return prompts


def _last_user_content(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
