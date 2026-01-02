"""LangChain AgentExecutor node for autonomous workflows."""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console

from pathlib import Path
from uuid import uuid4

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

    def __init__(self, workflow_config: Dict[str, Any] | None = None) -> None:
        self.role_prompts = self._load_role_prompts(workflow_config)
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
        backend_required = self._plan_requires_backend(phases) and repo_workspace is not None
        backend_handoff_ready = bool(phase_exec.get("backend_handoff_ready"))
        if backend_required:
            phase_exec["backend_required"] = True
        if prep_log:
            phase_exec["repo_prep"] = prep_log
        if repo_workspace:
            phase_exec["repo_path"] = str(repo_workspace)
        repo_branch = state.get("context", {}).get("target_branch")
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
            )
            instruction = self._format_phase_instruction(
                idx,
                phase,
                plan_request,
                repo_ref,
                repo_branch,
            )
            codex_result = self._invoke_codex(
                phase_idx=idx,
                phase=phase,
                feature_request=plan_request,
                repo_path=repo_ref,
                branch=repo_branch,
                session_id=session["id"],
                session_name=session["name"],
                phase_name=phase_name,
                instruction=instruction,
            )
            metadata.setdefault("codex_requests", []).append(
                {
                    "phase": phase_name,
                    "session_id": session["id"],
                    "session_name": session["name"],
                    "instruction": instruction,
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
                    followup_result = self._invoke_codex(
                        phase_idx=idx,
                        phase=phase,
                        feature_request=plan_request,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        session_id=session["id"],
                        session_name=session["name"],
                        phase_name=f"{phase_name} (handoff)",
                        instruction=followup_instruction,
                    )
                    metadata.setdefault("codex_requests", []).append(
                        {
                            "phase": f"{phase_name} (handoff)",
                            "session_id": session["id"],
                            "session_name": session["name"],
                            "instruction": followup_instruction,
                        }
                    )
                    phase_exec.setdefault("codex_calls", []).append(
                        {
                            "phase": f"{phase_name} (handoff)",
                            "result": followup_result,
                            "session_id": session["id"],
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
                    followup_result = self._invoke_codex(
                        phase_idx=idx,
                        phase=phase,
                        feature_request=plan_request,
                        repo_path=repo_ref,
                        branch=repo_branch,
                        session_id=session["id"],
                        session_name=session["name"],
                        phase_name=f"{phase_name} (handoff)",
                        instruction=followup_instruction,
                    )
                    metadata.setdefault("codex_requests", []).append(
                        {
                            "phase": f"{phase_name} (handoff)",
                            "session_id": session["id"],
                            "session_name": session["name"],
                            "instruction": followup_instruction,
                        }
                    )
                    phase_exec.setdefault("codex_calls", []).append(
                        {
                            "phase": f"{phase_name} (handoff)",
                            "result": followup_result,
                            "session_id": session["id"],
                        }
                    )
                    handoff_report = self._report_status(repo_workspace, report_path, required_sections)
                phase_exec.setdefault("handoff_reports", {})[phase_name] = handoff_report
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
            summary_lines.append(f"Codex CLI: {codex_result}")
            if handoff_report:
                summary_lines.append(
                    f"Handoff report: {handoff_report['path']} ({handoff_report['status']})"
                )
                missing = handoff_report.get("missing_sections")
                if missing:
                    summary_lines.append(f"Handoff report missing: {', '.join(missing)}")
            if followup_result:
                summary_lines.append(f"Codex CLI (handoff follow-up): {followup_result}")
            phase_output = "\n".join(summary_lines)
            phase_outputs.append(phase_output)
            checkpoints.append(
                {
                    "phase": phase_name,
                    "owners": owners,
                    "status": "executed",
                }
            )
            phase_exec.setdefault("codex_calls", []).append(
                {"phase": phase_name, "result": codex_result, "session_id": session["id"]}
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
        session_id: str | None,
        session_name: str | None,
        phase_name: str | None,
        instruction: str | None = None,
    ) -> str:
        instruction = instruction or self._format_phase_instruction(
            phase_idx,
            phase,
            feature_request,
            repo_path,
            branch,
        )
        try:
            return request_codex(
                instruction,
                repo_path=repo_path,
                branch=branch,
                session_id=session_id,
                session_name=session_name,
                phase=phase_name,
            )
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
        owners = self._phase_owners(phase)
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
        if is_backend_phase and report_path:
            lines.extend(
                [
                    "Backend handoff requirements:",
                    f"- Record Build, Tests, Run, and API Tests sections in {report_path}.",
                    "- Include exact commands, outcomes, and any failures/waivers.",
                ]
            )
        if is_frontend_phase and report_path:
            lines.extend(
                [
                    "Frontend handoff requirements:",
                    f"- Record Screens, Buttons, Flows, and UI Tests sections in {report_path}.",
                    "- Include exact commands, outcomes, and any failures/waivers.",
                ]
            )
        lines.append("Please implement this phase, run relevant tests, and ensure outputs align with guardrails.")
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
        result = request_codex(
            init_payload,
            repo_path=repo_path,
            branch=branch,
            session_id=session["id"],
            session_name=session["name"],
            phase=phase_name,
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
    def _normalize_role(value: str) -> str:
        return value.strip().lower().replace(" ", "_").replace("-", "_")

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
