"""Workflow nodes for the architect → reviewer → tech lead path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from rich.console import Console

from ..messages import append_message
from skills.codex_pack.tools import request_codex
from skills.implementation_pack.tools import dependency_matrix, phase_breakdown
from skills.lead_pack.tools import choose_stack, risk_matrix

console = Console()


def _last_user_message(state: Dict[str, Any]) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", "")).strip()
    return ""


def _dispatch_codex(
    plan: Dict[str, Any],
    phase: str,
    instructions: str,
    *,
    role_prompt: str | None = None,
) -> str:
    metadata = plan.setdefault("metadata", {})
    repo_path = metadata.get("repo_path")
    branch = metadata.get("target_branch")
    request_name = plan.get("request") or metadata.get("feature_request") or "feature"
    session = _ensure_codex_session(metadata, phase, request_name)
    _maybe_init_codex_session(
        metadata,
        phase,
        session,
        role_prompt,
        repo_path=repo_path,
        branch=branch,
    )
    lines = []
    if role_prompt:
        lines.append(f"Role prompt: {role_prompt.strip()}")
    lines.extend(
        [
            f"Feature request: {request_name}",
            f"Workflow phase: {phase}",
            instructions.strip(),
            "Update referenced files and return a short status summary.",
        ]
    )
    payload = "\n".join(lines)
    result = request_codex(
        payload,
        repo_path=repo_path,
        branch=branch,
        session_id=session["id"],
        session_name=session["name"],
        phase=phase,
    )
    metadata.setdefault("codex_logs", {})[phase] = result
    return result


def _ensure_codex_session(metadata: Dict[str, Any], phase: str, request_name: str) -> Dict[str, str]:
    sessions = metadata.setdefault("codex_sessions", {})
    session = sessions.get(phase)
    if session:
        return session
    session_id = uuid4().hex
    session_name = f"{request_name}:{phase}"
    session = {"id": session_id, "name": session_name}
    sessions[phase] = session
    return session


def _maybe_init_codex_session(
    metadata: Dict[str, Any],
    phase: str,
    session: Dict[str, str],
    role_prompt: str | None,
    *,
    repo_path: str | None,
    branch: str | None,
) -> None:
    role_prompt = (role_prompt or "").strip()
    if not role_prompt:
        return
    session_inits = metadata.setdefault("codex_session_inits", {})
    if phase in session_inits:
        return
    init_payload = "\n".join(
        [
            "Session init.",
            f"Role prompt: {role_prompt}",
            "Reply with a short acknowledgement. Await the next task.",
        ]
    )
    init_result = request_codex(
        init_payload,
        repo_path=repo_path,
        branch=branch,
        session_id=session["id"],
        session_name=session["name"],
        phase=phase,
    )
    session_inits[phase] = {"session_id": session["id"], "result": init_result}
    metadata.setdefault("codex_logs", {})[f"{phase}_init"] = init_result


def _coerce_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_phase_fields(
    phase: Dict[str, Any],
    *,
    default_owner: str | None = None,
    default_acceptance: List[str] | None = None,
) -> tuple[List[str], List[str]]:
    owners = _coerce_list(phase.get("owners") or phase.get("owner"))
    if not owners and default_owner:
        owners = [default_owner]
    if owners:
        phase["owners"] = owners
        phase.setdefault("owner", owners[0])
    acceptance_tests = _coerce_list(phase.get("acceptance_tests") or phase.get("acceptance"))
    if not acceptance_tests and default_acceptance:
        acceptance_tests = default_acceptance
    if acceptance_tests:
        phase["acceptance_tests"] = acceptance_tests
        phase.setdefault("acceptance", acceptance_tests)
    return owners, acceptance_tests


def _phase_issue_list(phases: List[Dict[str, Any]]) -> List[str]:
    issues: List[str] = []
    for idx, phase in enumerate(phases, start=1):
        name = phase.get("name", f"Phase {idx}")
        owners = _coerce_list(phase.get("owners") or phase.get("owner"))
        acceptance_tests = _coerce_list(phase.get("acceptance_tests") or phase.get("acceptance"))
        if not owners:
            issues.append(f"{name}: missing owners")
        if not acceptance_tests:
            issues.append(f"{name}: missing acceptance tests")
    return issues


class WorkflowSelectorNode:
    """Capture workflow metadata for downstream nodes."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        self.workflow_config = workflow_config

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        plan["request"] = request
        plan.setdefault("metadata", {})
        context = state.get("context", {})
        plan["metadata"].update(
            {
                "persona": context.get("persona", "architect"),
                "stack": context.get("stack", context.get("platform", "LangGraph POC")),
                "priority": context.get("priority", "standard"),
                "repo_path": context.get("repo_path") or context.get("repo"),
                "repo_url": context.get("repo_url"),
                "target_branch": context.get("target_branch") or context.get("branch"),
                "feature_request": context.get("feature_request") or request,
                "plan_only": context.get("plan_only"),
            }
        )
        state.setdefault("checkpoints", [])
        state.setdefault("attempt_counters", {})
        state["workflow_phase"] = "intake"
        repo_meta = plan["metadata"]
        repo_note = ""
        repo_ref = repo_meta.get("repo_path") or repo_meta.get("repo_url")
        if repo_ref:
            branch = repo_meta.get("target_branch")
            repo_note = f" Repo: {repo_ref}"
            if branch:
                repo_note += f" (branch {branch})"
        append_message(state, "system", f"Workflow intake captured feature request: {request}.{repo_note}")
        console.log(f"[magenta]WorkflowSelector[/] request='{request}' stack={plan['metadata']['stack']}")
        return state


class ArchitecturePlannerNode:
    """Produce a structured architecture plan."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.config = roles.get("architect", {})
        self.sections = self.config.get("sections", [])
        self.success_metric = self.config.get("success_metric", "")
        self.role_prompt = self.config.get("prompt")

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        persona = metadata.get("persona") or state.get("context", {}).get("persona", "architect")
        stack = metadata.get("stack") or state.get("context", {}).get("stack", "LangGraph POC")
        _dispatch_codex(
            plan,
            "architecture_planning",
            f"Create or update docs/plan.md with the architecture vision, system changes, guardrails, "
            f"success metrics, and key risks for '{request}'. Reference persona '{persona}' and stack '{stack}'. "
            "Include links to relevant knowledge-base files and ensure the document is well structured.",
            role_prompt=self.role_prompt,
        )
        summary_sections: List[Dict[str, str]] = []
        for section in self.sections:
            text = section.get("template", "").format(request=request, persona=persona, stack=stack)
            summary_sections.append({"title": section.get("title", "Section"), "content": text})
        if not summary_sections:
            summary_sections.append(
                {
                    "title": "Vision",
                    "content": f"Define how '{request}' leverages LangGraph workflow hooks.",
                }
            )
        architecture_plan = {
            "vision": summary_sections[0]["content"],
            "system_changes": (summary_sections[1]["content"] if len(summary_sections) > 1 else ""),
            "guardrails": (summary_sections[2]["content"] if len(summary_sections) > 2 else ""),
            "success_metric": self.success_metric.format(request=request, stack=stack)
            if self.success_metric
            else "Router reason recorded as workflow with checkpoints per gate.",
            "risks": risk_matrix(request),
        }
        plan["architecture"] = architecture_plan
        state.setdefault("artifacts", []).append(
            {
                "type": "architecture_plan",
                "request": request,
                "sections": summary_sections,
            }
        )
        state["workflow_phase"] = "architecture"
        state["checkpoints"].append({"phase": "architecture", "summary": architecture_plan["vision"]})
        append_message(
            state,
            "assistant",
            f"Architecture plan drafted for '{request}' covering {len(summary_sections)} sections.",
            name="architect",
        )
        console.log(f"[magenta]ArchitecturePlanner[/] drafted plan for '{request}'")
        return state


class PlanReviewerNode:
    """Validate the architecture plan and capture corrections."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.config = roles.get("reviewer", {})
        self.checklist = self.config.get("checklist", [])
        self.corrections = self.config.get("corrections", {})
        self.role_prompt = self.config.get("prompt")

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        phases = plan.get("phases") or []
        architecture = plan.setdefault("architecture", {})
        attempt_counters = state.setdefault("attempt_counters", {})
        phase_review = plan.get("phase_review") or {}

        if phases:
            phase_issues = phase_review.get("issues")
            if phase_issues is None:
                phase_issues = _phase_issue_list(phases)
            if phase_issues:
                attempt_counters["phase_review"] = attempt_counters.get("phase_review", 0) + 1
                context = state.get("context", {})
                metadata = plan.get("metadata") or {}
                persona = metadata.get("persona") or context.get("persona", "architect")
                scenario_id = context.get("scenario_id", "feature_request")
                scenario_file = context.get("scenario_file") or f"demo/{scenario_id}.yaml"
                for idx, phase in enumerate(phases, start=1):
                    default_owner = persona if idx == 1 else ("tech_lead" if idx == 2 else "ops")
                    _normalize_phase_fields(
                        phase,
                        default_owner=default_owner,
                        default_acceptance=[f"Scenario validation: {scenario_file}"],
                    )
                plan["phase_review"] = {
                    "status": "pending",
                    "issues": phase_issues,
                    "attempts": attempt_counters["phase_review"],
                }
                state["workflow_phase"] = "phase_review"
                if attempt_counters["phase_review"] == 1:
                    _dispatch_codex(
                        plan,
                        "phase_review",
                        "Review docs/implementation.md and docs/plan.md to ensure every phase lists owners and "
                        "acceptance tests. Address the following gaps: "
                        f"{', '.join(phase_issues)}. Update the docs and summarize the corrections.",
                        role_prompt=self.role_prompt,
                    )
                    feedback = "Reviewer requested updates for phase owners/acceptance tests."
                    plan.setdefault("review_feedback", []).append(feedback)
                    append_message(state, "assistant", feedback, name="plan_reviewer")
                    console.log("[yellow]PlanReviewer[/] requested phase corrections")
                    raise ValueError("Reviewer sent phase corrections")
                plan["phase_review"]["status"] = "approved"
                state.setdefault("checkpoints", []).append({"phase": "phase_review", "status": "approved"})
                append_message(state, "assistant", "Plan reviewer approved phase corrections.", name="plan_reviewer")
                console.log("[green]PlanReviewer[/] approved phase corrections")
                return state

        missing: List[str] = []
        if not architecture.get("acceptance_tests"):
            architecture["acceptance_tests"] = [
                "demo/feature_request.yaml exercises the workflow branch end-to-end.",
                "IO audit logs route=workflow with valid_input/valid_output true.",
            ]
            missing.append("acceptance tests")
        if not architecture.get("guardrails") or isinstance(architecture.get("guardrails"), str):
            architecture["guardrails"] = [
                self.corrections.get("guardrails")
                or "List docs/plan.md + telemetry guardrails before merging the workflow."
            ]
            missing.append("guardrails")

        state["workflow_phase"] = "review"
        attempt_counters["plan_review"] = attempt_counters.get("plan_review", 0) + 1
        if missing and attempt_counters["plan_review"] == 1:
            _dispatch_codex(
                plan,
                "architecture_review",
                "Review docs/plan.md for the feature, address the following gaps: "
                f"{', '.join(missing)}. Update the document with reviewer notes and request any fixes.",
                role_prompt=self.role_prompt,
            )
            feedback = f"Reviewer requested updates for: {', '.join(missing)}."
            plan.setdefault("review_feedback", []).append(feedback)
            append_message(state, "assistant", feedback, name="plan_reviewer")
            console.log("[yellow]PlanReviewer[/] requested corrections")
            raise ValueError("Reviewer sent corrections")

        plan["review"] = {
            "status": "approved",
            "checklist": self.checklist,
            "attempts": attempt_counters["plan_review"],
        }
        state["workflow_phase"] = "review_approved"
        state["checkpoints"].append({"phase": "review", "status": "approved"})
        _dispatch_codex(
            plan,
            "architecture_review",
            "Confirm reviewer approval in docs/plan.md by adding a 'Reviewer Sign-off' section summarizing "
            "acceptance tests and guardrails for this feature.",
            role_prompt=self.role_prompt,
        )
        append_message(state, "assistant", "Plan reviewer approved the architecture.", name="plan_reviewer")
        console.log("[green]PlanReviewer[/] approved plan")
        return state


class TechLeadNode:
    """Convert the approved plan into executable milestones."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.config = roles.get("tech_lead", {})
        self.phases = self.config.get("phases", [])
        self.dependencies = self.config.get("dependencies", [])
        self.intro = self.config.get("intro", "")
        self.role_prompt = self.config.get("prompt")

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        stack = metadata.get("stack", state.get("context", {}).get("stack", "LangGraph POC"))
        _dispatch_codex(
            plan,
            "tech_lead_planning",
            "Produce the Tech Lead plan for this feature in docs/plan.md (or docs/feature.md) including "
            "stack recommendations, dependencies, guardrails, and a numbered list of phases with focus areas. "
            "Ensure the document references the reviewer-approved guardrails.",
            role_prompt=self.role_prompt,
        )

        phase_entries = [
            {"name": cfg.get("name", f"Phase {idx+1}"), "focus": cfg.get("focus", "")}
            for idx, cfg in enumerate(self.phases)
        ]
        if not phase_entries:
            phase_entries = [
                {"name": "Design", "focus": "Finalize prompts + docs"},
                {"name": "Implementation", "focus": "Land workflow nodes"},
            ]

        deliverables = phase_breakdown(request, [phase["name"] for phase in phase_entries])
        dependency_notes = dependency_matrix(request)

        implementation_plan = {
            "stack_recommendation": choose_stack(request, stack),
            "phases": phase_entries,
            "deliverables": deliverables,
            "dependencies": {**dependency_notes, "Additional": "; ".join(self.dependencies)},
        }
        plan["implementation"] = implementation_plan

        artifact = {
            "type": "tech_lead_plan",
            "request": request,
            "phases": phase_entries,
            "deliverables": deliverables,
            "dependencies": implementation_plan["dependencies"],
        }
        state.setdefault("artifacts", []).append(artifact)
        state["workflow_phase"] = "tech_lead"
        state["checkpoints"].append({"phase": "tech_lead", "phases": [phase["name"] for phase in phase_entries]})

        summary_lines = [
            f"## Tech Lead Plan for {request}",
            self.intro,
            f"- Stack guidance: {implementation_plan['stack_recommendation']}",
            "### Phases",
        ]
        for deliverable in deliverables:
            summary_lines.append(f"* {deliverable}")
        summary_lines.append("### Dependencies & Guardrails")
        for dep, reason in implementation_plan["dependencies"].items():
            summary_lines.append(f"* {dep}: {reason}")
        summary_lines.append("### Risks (echoed from reviewer)")
        for risk in plan.get("architecture", {}).get("risks", []):
            summary_lines.append(f"* {risk}")

        output = "\n".join(line for line in summary_lines if line.strip())
        state["output"] = output
        append_message(state, "assistant", output, name="tech_lead")
        console.log(f"[cyan]TechLeadNode[/] published execution plan for '{request}'")
        return state


class ImplementationPlannerNode:
    """Convert approved plans into phase-wise execution slices."""

    def __init__(self, workflow_config: Dict[str, Any] | None = None, template_path: str = "docs/implementation.md") -> None:
        self.template_path = Path(template_path)
        roles = (workflow_config or {}).get("roles", {})
        self.role_prompt = (roles.get("tech_lead", {}) or {}).get("prompt")
        self.default_phases = [
            {"name": "Design Hardening", "focus": "Finalize architecture + docs for {request}."},
            {"name": "Implementation", "focus": "Land workflow nodes + telemetry for {request}."},
            {"name": "Validation", "focus": "Run demo scenarios + tests proving {request} works."},
        ]

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        review_status = (plan.get("review") or {}).get("status")
        if review_status != "approved":
            raise ValueError("Implementation planner requires an approved review state.")
        _dispatch_codex(
            plan,
            "implementation_planning",
            "Break the implementation into phases (Design Hardening, Implementation, Validation) inside "
            "docs/implementation.md or docs/plan.md. For each phase list owner, deliverables, and acceptance "
            "criteria, and capture a machine-readable summary if possible.",
            role_prompt=self.role_prompt,
        )
        template_sections = self._load_template_sections()
        request = plan.get("request") or _last_user_message(state)
        context = state.get("context", {})
        metadata = plan.setdefault("metadata", {})
        persona = metadata.get("persona") or context.get("persona", "architect")
        scenario_id = context.get("scenario_id", "feature_request")
        scenario_file = context.get("scenario_file") or f"demo/{scenario_id}.yaml"
        owners = context.get("phase_owners") or {}

        phases: List[Dict[str, Any]] = []
        for idx, base in enumerate(self.default_phases, start=1):
            name = base["name"]
            owner = owners.get(name)
            if not owner:
                owner = persona if idx == 1 else ("tech_lead" if idx == 2 else "ops")
            deliverables = [
                base["focus"].format(request=request),
                template_sections["template"],
                template_sections["dependencies"],
            ]
            acceptance_tests = [
                template_sections["checklist"],
                f"Scenario validation: {scenario_file}",
            ]
            owners_list = _coerce_list(owner)
            if not owners_list:
                owners_list = [str(owner)]
            phases.append(
                {
                    "name": name,
                    "owners": owners_list,
                    "deliverables": deliverables,
                    "acceptance_tests": acceptance_tests,
                    "owner": owners_list[0] if owners_list else owner,
                    "acceptance": acceptance_tests,
                }
            )

        plan["phases"] = phases
        artifact = {
            "type": "phases",
            "request": request,
            "phases": phases,
        }
        state.setdefault("artifacts", []).append(artifact)
        state["workflow_phase"] = "implementation_planning"
        state.setdefault("checkpoints", []).append({"phase": "implementation_planning", "phases": [p["name"] for p in phases]})
        summary = "Implementation planner created phase breakdown:\n" + "\n".join(
            f"- {p['name']} (owners: {', '.join(p.get('owners') or [p.get('owner', 'unknown')])})"
            for p in phases
        )
        append_message(state, "assistant", summary, name="implementation_planner")
        console.log(f"[cyan]ImplementationPlanner[/] generated {len(phases)} phases for '{request}'")
        return state

    def _load_template_sections(self) -> Dict[str, str]:
        if not self.template_path.exists():
            raise FileNotFoundError(f"Implementation template missing: {self.template_path}")
        text = self.template_path.read_text(encoding="utf-8")
        return {
            "template": self._extract_section(text, "Phase Template"),
            "dependencies": self._extract_section(text, "Dependencies & Guardrails"),
            "checklist": self._extract_section(text, "Review Checklist"),
        }

    @staticmethod
    def _extract_section(text: str, header: str) -> str:
        marker = f"## {header}"
        if marker not in text:
            raise ValueError(f"Section '{header}' missing from implementation guide")
        segment = text.split(marker, 1)[1]
        lines = []
        for line in segment.splitlines():
            if line.startswith("## "):
                break
            if line.strip():
                lines.append(line.strip())
        return " ".join(lines) or header


class PlanValidatorNode:
    """Validate phases before execution and route back to reviewer if needed."""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        phases = plan.get("phases") or []
        issues: List[str] = []
        for idx, phase in enumerate(phases, start=1):
            name = phase.get("name", f"Phase {idx}")
            owners, acceptance_tests = _normalize_phase_fields(phase)
            if not owners:
                issues.append(f"{name}: missing owners")
            if not acceptance_tests:
                issues.append(f"{name}: missing acceptance tests")
        if issues:
            plan["phase_review"] = {"status": "needs_review", "issues": issues}
            append_message(
                state,
                "assistant",
                "Phase validation failed; routing back to reviewer for corrections.",
                name="plan_validator",
            )
        else:
            plan.pop("phase_review", None)
        state["workflow_phase"] = "phase_validation"
        return state

    def branch(self, state: Dict[str, Any]) -> str:
        phase_review = (state.get("plan") or {}).get("phase_review") or {}
        issues = phase_review.get("issues") or []
        return "needs_review" if issues else "ok"
