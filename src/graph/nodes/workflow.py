"""Workflow nodes for the product → design → architecture → lead → tech lead path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from rich.console import Console

from ..messages import append_message
from skills.codex_pack.tools import request_codex
from skills.gemini_pack.tools import request_gemini
from skills.implementation_pack.tools import dependency_matrix, phase_breakdown
from skills.lead_pack.tools import choose_stack, risk_matrix

console = Console()


def _role_output_file(role_config: Dict[str, Any], fallback: str) -> str:
    value = (role_config or {}).get("output_file") or fallback
    return str(value)


def _select_lead_role(
    selector: Dict[str, Any],
    request: str,
    roles: Dict[str, Any],
) -> str | None:
    text = (request or "").lower()
    rules = (selector or {}).get("rules") or []
    for rule in rules:
        role = rule.get("role")
        keywords = rule.get("keywords") or []
        if role and any(str(keyword).lower() in text for keyword in keywords):
            return role if role in roles else None
    default_role = (selector or {}).get("default")
    if default_role and default_role in roles:
        return default_role
    for key in roles:
        if key.startswith("lead_"):
            return key
    return default_role


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
    metadata.setdefault("codex_requests", []).append(
        {
            "phase": phase,
            "session_id": session["id"],
            "session_name": session["name"],
            "instruction": payload,
        }
    )
    metadata.setdefault("codex_logs", {})[phase] = result
    return result


def _dispatch_gemini(
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
    session = _ensure_gemini_session(metadata, phase, request_name)
    _maybe_init_gemini_session(
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
    result = request_gemini(
        payload,
        repo_path=repo_path,
        branch=branch,
        session_id=session["id"],
        session_name=session["name"],
        phase=phase,
    )
    metadata.setdefault("gemini_requests", []).append(
        {
            "phase": phase,
            "session_id": session["id"],
            "session_name": session["name"],
            "instruction": payload,
        }
    )
    metadata.setdefault("gemini_logs", {})[phase] = result
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


def _ensure_gemini_session(metadata: Dict[str, Any], phase: str, request_name: str) -> Dict[str, str]:
    sessions = metadata.setdefault("gemini_sessions", {})
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


def _maybe_init_gemini_session(
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
    session_inits = metadata.setdefault("gemini_session_inits", {})
    if phase in session_inits:
        return
    init_payload = "\n".join(
        [
            "Session init.",
            f"Role prompt: {role_prompt}",
            "Reply with a short acknowledgement. Await the next task.",
        ]
    )
    init_result = request_gemini(
        init_payload,
        repo_path=repo_path,
        branch=branch,
        session_id=session["id"],
        session_name=session["name"],
        phase=phase,
    )
    session_inits[phase] = {"session_id": session["id"], "result": init_result}
    metadata.setdefault("gemini_logs", {})[f"{phase}_init"] = init_result


def _coerce_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_workflow_mode(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"full", "all"}:
        return "full"
    if text in {"from_planning", "post_planning", "resume"}:
        return "from_planning"
    if text in {"planning", "planning_only", "plan_only", "architecture_only"}:
        return "planning"
    return "planning"


def _extract_markdown_section(text: str, header: str) -> str:
    marker = f"## {header}"
    if marker not in text:
        return ""
    segment = text.split(marker, 1)[1]
    lines: List[str] = []
    for line in segment.splitlines():
        if line.startswith("## "):
            break
        lines.append(line.rstrip())
    return "\n".join(line for line in lines if line.strip()).strip()


def _markdown_list(section: str) -> List[str]:
    items: List[str] = []
    for line in section.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        if trimmed.startswith(("-", "*")):
            trimmed = trimmed.lstrip("-*").strip()
        items.append(trimmed)
    return items


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
        workflow_mode = _normalize_workflow_mode(context.get("workflow_mode"))
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
                "workflow_mode": workflow_mode,
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


class ProductOwnerNode:
    """Refine the feature request before design + architecture."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.config = roles.get("product_owner", {})
        self.role_prompt = self.config.get("prompt")
        self.output_file = _role_output_file(self.config, "docs/product_plan.md")
        self.runner = (self.config.get("runner") or "codex").lower()
        self.gemini_config = roles.get("gemini_product_reviewer", {})
        self.gemini_prompt = self.gemini_config.get("prompt")
        self.gemini_output_file = _role_output_file(
            self.gemini_config,
            "docs/gemini_product_review.md",
        )
        self.gemini_runner = (self.gemini_config.get("runner") or "gemini").lower()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        metadata["product_file"] = self.output_file
        instructions = (
            f"Enhance the feature request '{request}' in {self.output_file}. "
            "Include user intent, value metric, scenario sketch, and system constraints. "
            "Call out dependencies that architecture and UI/UX must respect. "
            f"Only edit {self.output_file}."
        )
        if self.runner == "gemini":
            _dispatch_gemini(plan, "product_owner", instructions, role_prompt=self.role_prompt)
        else:
            _dispatch_codex(plan, "product_owner", instructions, role_prompt=self.role_prompt)
        if self.gemini_config:
            metadata["product_review_file"] = self.gemini_output_file
            review_instructions = (
                f"Review {self.output_file} for '{request}'. Provide suggestions only, do not rewrite the plan. "
                f"Capture feedback in {self.gemini_output_file}. Only edit {self.gemini_output_file}."
            )
            if self.gemini_runner == "gemini":
                _dispatch_gemini(plan, "product_review", review_instructions, role_prompt=self.gemini_prompt)
            else:
                _dispatch_codex(plan, "product_review", review_instructions, role_prompt=self.gemini_prompt)
            update_instructions = (
                f"Update {self.output_file} using suggestions in {self.gemini_output_file}. "
                f"Only edit {self.output_file}."
            )
            _dispatch_codex(plan, "product_owner_update", update_instructions, role_prompt=self.role_prompt)
        state.setdefault("artifacts", []).append(
            {"type": "product_plan", "request": request, "file": self.output_file}
        )
        state["workflow_phase"] = "product_owner"
        state.setdefault("checkpoints", []).append({"phase": "product_owner", "file": self.output_file})
        append_message(state, "assistant", "Product owner refined the request.", name="product_owner")
        console.log(f"[magenta]ProductOwner[/] updated {self.output_file}")
        return state


class UiUxDesignerNode:
    """Translate the product plan into UX guidance."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.config = roles.get("ui_ux_designer", {})
        self.role_prompt = self.config.get("prompt")
        self.output_file = _role_output_file(self.config, "docs/ui_ux_plan.md")
        self.runner = (self.config.get("runner") or "codex").lower()
        self.gemini_config = roles.get("gemini_ui_ux_reviewer", {})
        self.gemini_prompt = self.gemini_config.get("prompt")
        self.gemini_output_file = _role_output_file(
            self.gemini_config,
            "docs/gemini_ui_ux_review.md",
        )
        self.gemini_runner = (self.gemini_config.get("runner") or "gemini").lower()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        product_file = metadata.get("product_file") or "docs/product_plan.md"
        metadata["ui_ux_file"] = self.output_file
        instructions = (
            f"Design the UX for '{request}' using {product_file} as input. "
            f"Document flows, screens, component mapping, and interaction hints in {self.output_file}. "
            f"Include responsive considerations and accessibility notes. Only edit {self.output_file}."
        )
        if self.runner == "gemini":
            _dispatch_gemini(plan, "ui_ux_design", instructions, role_prompt=self.role_prompt)
        else:
            _dispatch_codex(plan, "ui_ux_design", instructions, role_prompt=self.role_prompt)
        if self.gemini_config:
            metadata["ui_ux_review_file"] = self.gemini_output_file
            review_instructions = (
                f"Review {self.output_file} for '{request}'. Provide UX/UI suggestions only. "
                f"Capture feedback in {self.gemini_output_file}. Only edit {self.gemini_output_file}."
            )
            if self.gemini_runner == "gemini":
                _dispatch_gemini(plan, "ui_ux_review", review_instructions, role_prompt=self.gemini_prompt)
            else:
                _dispatch_codex(plan, "ui_ux_review", review_instructions, role_prompt=self.gemini_prompt)
            update_instructions = (
                f"Update {self.output_file} using suggestions in {self.gemini_output_file}. "
                f"Only edit {self.output_file}."
            )
            _dispatch_codex(plan, "ui_ux_update", update_instructions, role_prompt=self.role_prompt)
        state.setdefault("artifacts", []).append(
            {"type": "ui_ux_plan", "request": request, "file": self.output_file}
        )
        state["workflow_phase"] = "ui_ux_design"
        state.setdefault("checkpoints", []).append({"phase": "ui_ux_design", "file": self.output_file})
        append_message(state, "assistant", "UI/UX design documented.", name="ui_ux_designer")
        console.log(f"[magenta]UiUxDesigner[/] updated {self.output_file}")
        return state


class ArchitecturePlannerNode:
    """Produce a structured architecture plan."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.config = roles.get("architect", {})
        self.sections = self.config.get("sections", [])
        self.success_metric = self.config.get("success_metric", "")
        self.role_prompt = self.config.get("prompt")
        self.output_file = _role_output_file(self.config, "docs/architecture_plan.md")
        self.runner = (self.config.get("runner") or "codex").lower()
        self.gemini_config = roles.get("gemini_arch_reviewer", {})
        self.gemini_prompt = self.gemini_config.get("prompt")
        self.gemini_output_file = _role_output_file(
            self.gemini_config,
            "docs/gemini_arch_review.md",
        )
        self.gemini_runner = (self.gemini_config.get("runner") or "gemini").lower()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        context = state.get("context") or {}
        persona = metadata.get("persona") or state.get("context", {}).get("persona", "architect")
        stack = metadata.get("stack") or state.get("context", {}).get("stack", "LangGraph POC")
        product_file = metadata.get("product_file") or "docs/product_plan.md"
        ui_ux_file = metadata.get("ui_ux_file") or "docs/ui_ux_plan.md"
        scenario_id = context.get("scenario_id", "feature_request")
        scenario_file = context.get("scenario_file") or f"demo/{scenario_id}.yaml"
        metadata["architecture_file"] = self.output_file
        instructions = (
            f"Create or update {self.output_file} with the architecture vision, system changes, guardrails, "
            f"success metrics, API design, and key risks for '{request}'. Reference persona '{persona}' and "
            f"stack '{stack}'. Incorporate inputs from {product_file} and {ui_ux_file}. Include links to "
            f"relevant knowledge-base files and include acceptance tests referencing {scenario_file}. "
            "Ensure the document is well structured. "
            f"Only edit {self.output_file}."
        )
        if self.runner == "gemini":
            _dispatch_gemini(plan, "architecture_planning", instructions, role_prompt=self.role_prompt)
        else:
            _dispatch_codex(plan, "architecture_planning", instructions, role_prompt=self.role_prompt)
        if self.gemini_config:
            metadata["architecture_review_file"] = self.gemini_output_file
            review_instructions = (
                f"Review {self.output_file} for '{request}'. Provide architecture suggestions only. "
                f"Capture feedback in {self.gemini_output_file}. Only edit {self.gemini_output_file}."
            )
            if self.gemini_runner == "gemini":
                _dispatch_gemini(plan, "architecture_review", review_instructions, role_prompt=self.gemini_prompt)
            else:
                _dispatch_codex(plan, "architecture_review", review_instructions, role_prompt=self.gemini_prompt)
            update_instructions = (
                f"Update {self.output_file} using suggestions in {self.gemini_output_file}. "
                f"Only edit {self.output_file}."
            )
            _dispatch_codex(plan, "architecture_update", update_instructions, role_prompt=self.role_prompt)
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
        section_map = {section["title"].lower(): section["content"] for section in summary_sections}
        architecture_plan = {
            "vision": section_map.get("vision", ""),
            "system_changes": section_map.get("system surface", ""),
            "guardrails": section_map.get("guardrails", ""),
            "api_design": section_map.get("api design", ""),
            "success_metric": self.success_metric.format(request=request, stack=stack)
            if self.success_metric
            else "Router reason recorded as workflow with checkpoints per gate.",
            "risks": risk_matrix(request),
            "acceptance_tests": [
                f"{scenario_file} exercises the workflow branch end-to-end.",
                "IO audit logs route=workflow with valid_input/valid_output true.",
            ],
        }
        plan["architecture"] = architecture_plan
        state.setdefault("artifacts", []).append(
            {
                "type": "architecture_plan",
                "request": request,
                "sections": summary_sections,
                "file": self.output_file,
            }
        )
        state["workflow_phase"] = "architecture"
        state["checkpoints"].append({"phase": "architecture", "summary": architecture_plan["vision"]})
        state["output"] = f"Architecture plan drafted in {self.output_file}."
        append_message(
            state,
            "assistant",
            f"Architecture plan drafted for '{request}' covering {len(summary_sections)} sections.",
            name="architect",
        )
        console.log(f"[magenta]ArchitecturePlanner[/] drafted plan for '{request}'")
        return state


class PlanningResumeNode:
    """Seed planning metadata when resuming after architecture."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.product_file = _role_output_file(roles.get("product_owner", {}), "docs/product_plan.md")
        self.ui_ux_file = _role_output_file(roles.get("ui_ux_designer", {}), "docs/ui_ux_plan.md")
        self.architecture_file = _role_output_file(roles.get("architect", {}), "docs/architecture_plan.md")

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        metadata = plan.setdefault("metadata", {})
        metadata.setdefault("product_file", self.product_file)
        metadata.setdefault("ui_ux_file", self.ui_ux_file)
        metadata.setdefault("architecture_file", self.architecture_file)
        architecture = plan.setdefault("architecture", {})

        path = Path(self.architecture_file)
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if not architecture.get("vision"):
                vision = _extract_markdown_section(text, "Vision")
                if vision:
                    architecture["vision"] = vision
            if not architecture.get("guardrails"):
                guardrails = _extract_markdown_section(text, "Guardrails")
                if guardrails:
                    architecture["guardrails"] = _markdown_list(guardrails)
            if not architecture.get("api_design"):
                api_design = _extract_markdown_section(text, "API Design")
                if api_design:
                    architecture["api_design"] = api_design
            if not architecture.get("acceptance_tests"):
                acceptance = _extract_markdown_section(text, "Acceptance Tests")
                if not acceptance:
                    acceptance = _extract_markdown_section(text, "Acceptance")
                if acceptance:
                    architecture["acceptance_tests"] = _markdown_list(acceptance)

        state["workflow_phase"] = "planning_resume"
        state.setdefault("checkpoints", []).append(
            {"phase": "planning_resume", "file": self.architecture_file}
        )
        append_message(state, "assistant", "Planning resume initialized.", name="planning_resume")
        console.log("[magenta]PlanningResume[/] seeded planning metadata")
        return state


class GeminiReviewNode:
    """Use Gemini to review product, UX, and architecture plans."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.config = roles.get("gemini_reviewer", {})
        self.role_prompt = self.config.get("prompt")
        self.output_file = _role_output_file(self.config, "docs/gemini_review.md")
        self.runner = (self.config.get("runner") or "gemini").lower()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        product_file = metadata.get("product_file") or "docs/product_plan.md"
        ui_ux_file = metadata.get("ui_ux_file") or "docs/ui_ux_plan.md"
        architecture_file = metadata.get("architecture_file") or "docs/architecture_plan.md"
        metadata["gemini_review_file"] = self.output_file
        instructions = (
            f"Review {product_file}, {ui_ux_file}, and {architecture_file} for '{request}'. "
            f"Call out gaps, inconsistencies, missing telemetry, and API risks. Summarize findings and "
            f"actionable recommendations in {self.output_file}. Only edit {self.output_file}."
        )
        if self.runner == "gemini":
            _dispatch_gemini(plan, "gemini_review", instructions, role_prompt=self.role_prompt)
        else:
            _dispatch_codex(plan, "gemini_review", instructions, role_prompt=self.role_prompt)
        state.setdefault("artifacts", []).append(
            {"type": "gemini_review", "request": request, "file": self.output_file}
        )
        state["workflow_phase"] = "gemini_review"
        state.setdefault("checkpoints", []).append({"phase": "gemini_review", "file": self.output_file})
        append_message(state, "assistant", "Gemini review completed.", name="gemini_reviewer")
        console.log(f"[magenta]GeminiReview[/] updated {self.output_file}")
        return state


class PlanReviewerNode:
    """Validate the architecture plan and capture corrections."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.config = roles.get("reviewer", {})
        self.checklist = self.config.get("checklist", [])
        self.corrections = self.config.get("corrections", {})
        self.role_prompt = self.config.get("prompt")
        self.output_file = _role_output_file(self.config, "docs/review_notes.md")

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        phases = plan.get("phases") or []
        architecture = plan.setdefault("architecture", {})
        attempt_counters = state.setdefault("attempt_counters", {})
        phase_review = plan.get("phase_review") or {}
        metadata = plan.setdefault("metadata", {})
        metadata["review_file"] = self.output_file
        implementation_file = metadata.get("implementation_file") or "docs/implementation.md"
        architecture_file = metadata.get("architecture_file") or "docs/architecture_plan.md"
        product_file = metadata.get("product_file") or "docs/product_plan.md"
        ui_ux_file = metadata.get("ui_ux_file") or "docs/ui_ux_plan.md"

        if phases:
            phase_issues = phase_review.get("issues")
            if phase_issues is None:
                phase_issues = _phase_issue_list(phases)
            if phase_issues:
                attempt_counters["phase_review"] = attempt_counters.get("phase_review", 0) + 1
                plan["phase_review"] = {
                    "status": "needs_revision",
                    "issues": phase_issues,
                    "attempts": attempt_counters["phase_review"],
                }
                state["workflow_phase"] = "phase_review"
                _dispatch_codex(
                    plan,
                    "phase_review",
                    f"Review {implementation_file} to ensure every phase lists owners and acceptance tests. "
                    f"Document requested corrections in {self.output_file} only. Issues: {', '.join(phase_issues)}.",
                    role_prompt=self.role_prompt,
                )
                feedback = "Reviewer requested updates for phase owners/acceptance tests."
                plan.setdefault("review_feedback", []).append(feedback)
                append_message(state, "assistant", feedback, name="plan_reviewer")
                console.log("[yellow]PlanReviewer[/] requested phase corrections")
                return state
            if phase_review:
                plan["phase_review"] = {
                    "status": "approved",
                    "issues": [],
                    "attempts": attempt_counters.get("phase_review", 0),
                }
                state.setdefault("checkpoints", []).append({"phase": "phase_review", "status": "approved"})
                append_message(state, "assistant", "Plan reviewer approved phase corrections.", name="plan_reviewer")
                console.log("[green]PlanReviewer[/] approved phase corrections")

        missing: List[str] = []
        if not architecture.get("acceptance_tests"):
            missing.append("acceptance tests")
        if not architecture.get("guardrails"):
            missing.append("guardrails")

        attempt_counters["plan_review"] = attempt_counters.get("plan_review", 0) + 1
        if missing:
            plan["review"] = {
                "status": "needs_revision",
                "issues": missing,
                "attempts": attempt_counters["plan_review"],
            }
            state["workflow_phase"] = "review_needs_revision"
            _dispatch_codex(
                plan,
                "architecture_review",
                f"Review {architecture_file}, {product_file}, and {ui_ux_file} for the feature. "
                f"Document missing items and requested corrections in {self.output_file} only. "
                f"Missing: {', '.join(missing)}.",
                role_prompt=self.role_prompt,
            )
            feedback = f"Reviewer requested updates for: {', '.join(missing)}."
            plan.setdefault("review_feedback", []).append(feedback)
            append_message(state, "assistant", feedback, name="plan_reviewer")
            console.log("[yellow]PlanReviewer[/] requested corrections")
            return state

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
            f"Record reviewer approval in {self.output_file} with a 'Reviewer Sign-off' section that "
            "summarizes acceptance tests and guardrails for this feature. Only edit the review notes file.",
            role_prompt=self.role_prompt,
        )
        append_message(state, "assistant", "Plan reviewer approved the architecture.", name="plan_reviewer")
        console.log("[green]PlanReviewer[/] approved plan")
        return state

    def branch(self, state: Dict[str, Any]) -> str:
        plan = state.get("plan") or {}
        phase_review = plan.get("phase_review") or {}
        if phase_review.get("status") == "needs_revision":
            return "phase_revision"
        review = plan.get("review") or {}
        if review.get("status") == "needs_revision":
            return "architecture_revision"
        return "approved"


class LeadPlannerNode:
    """Pick a lead role based on request and record a lead plan."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        self.roles = workflow_config.get("roles", {})
        self.selector = workflow_config.get("lead_selector", {})

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        role_key = _select_lead_role(self.selector, request, self.roles)
        if not role_key:
            state["workflow_phase"] = "lead_planning_skipped"
            append_message(state, "assistant", "No lead role matched; skipping lead plan.", name="lead_planner")
            console.log("[yellow]LeadPlanner[/] no matching lead role")
            return state
        lead_config = self.roles.get(role_key, {})
        role_prompt = lead_config.get("prompt")
        output_file = _role_output_file(lead_config, f"docs/{role_key}_plan.md")
        metadata["lead_role"] = role_key
        metadata["lead_file"] = output_file
        product_file = metadata.get("product_file") or "docs/product_plan.md"
        ui_ux_file = metadata.get("ui_ux_file") or "docs/ui_ux_plan.md"
        architecture_file = metadata.get("architecture_file") or "docs/architecture_plan.md"
        review_file = metadata.get("review_file") or "docs/review_notes.md"
        focus = lead_config.get("focus") or []
        focus_text = "; ".join(str(item) for item in focus if str(item).strip())
        instructions = (
            f"Create a lead plan for '{request}' in {output_file}. "
            f"Use {product_file}, {ui_ux_file}, {architecture_file}, and {review_file}. "
            f"Focus areas: {focus_text or 'prioritize domain-specific risks and tests'}. "
            f"Only edit {output_file}."
        )
        _dispatch_codex(plan, f"{role_key}_planning", instructions, role_prompt=role_prompt)
        plan["lead"] = {"role": role_key, "file": output_file, "focus": focus}
        state.setdefault("artifacts", []).append(
            {"type": "lead_plan", "request": request, "role": role_key, "file": output_file}
        )
        state["workflow_phase"] = "lead_planning"
        state.setdefault("checkpoints", []).append({"phase": "lead_planning", "role": role_key, "file": output_file})
        append_message(state, "assistant", f"Lead plan created for {role_key}.", name="lead_planner")
        console.log(f"[magenta]LeadPlanner[/] selected {role_key}")
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
        self.output_file = _role_output_file(self.config, "docs/tech_lead_plan.md")

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        metadata["tech_lead_file"] = self.output_file
        stack = metadata.get("stack", state.get("context", {}).get("stack", "LangGraph POC"))
        product_file = metadata.get("product_file") or "docs/product_plan.md"
        ui_ux_file = metadata.get("ui_ux_file") or "docs/ui_ux_plan.md"
        architecture_file = metadata.get("architecture_file") or "docs/architecture_plan.md"
        review_file = metadata.get("review_file") or "docs/review_notes.md"
        lead_file = metadata.get("lead_file") or "docs/lead_plan.md"
        _dispatch_codex(
            plan,
            "tech_lead_planning",
            f"Produce the Tech Lead plan for this feature in {self.output_file} including stack recommendations, "
            "dependencies, guardrails, and a numbered list of phases with focus areas. Reference "
            f"{product_file}, {ui_ux_file}, {architecture_file}, {lead_file}, and {review_file}. "
            f"Only edit {self.output_file}.",
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
        role_config = roles.get("implementation_planner", {}) or {}
        self.role_prompt = role_config.get("prompt")
        self.output_file = _role_output_file(role_config, str(self.template_path))
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
        metadata = plan.setdefault("metadata", {})
        metadata["implementation_file"] = self.output_file
        _dispatch_codex(
            plan,
            "implementation_planning",
            "Break the implementation into phases (Design Hardening, Implementation, Validation) inside "
            f"{self.output_file}. For each phase list owner, deliverables, and acceptance criteria, and "
            "capture a machine-readable summary if possible. Only edit the implementation file.",
            role_prompt=self.role_prompt,
        )
        template_sections = self._load_template_sections()
        request = plan.get("request") or _last_user_message(state)
        context = state.get("context", {})
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
