"""Workflow nodes for the architect → reviewer → tech lead path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console

from ..messages import append_message
from skills.implementation_pack.tools import dependency_matrix, phase_breakdown
from skills.lead_pack.tools import choose_stack, risk_matrix

console = Console()


def _last_user_message(state: Dict[str, Any]) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", "")).strip()
    return ""


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
            }
        )
        state.setdefault("checkpoints", [])
        state.setdefault("attempt_counters", {})
        state["workflow_phase"] = "intake"
        append_message(state, "system", f"Workflow intake captured feature request: {request}")
        console.log(f"[magenta]WorkflowSelector[/] request='{request}' stack={plan['metadata']['stack']}")
        return state


class ArchitecturePlannerNode:
    """Produce a structured architecture plan."""

    def __init__(self, workflow_config: Dict[str, Any]) -> None:
        roles = workflow_config.get("roles", {})
        self.config = roles.get("architect", {})
        self.sections = self.config.get("sections", [])
        self.success_metric = self.config.get("success_metric", "")

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        persona = metadata.get("persona") or state.get("context", {}).get("persona", "architect")
        stack = metadata.get("stack") or state.get("context", {}).get("stack", "LangGraph POC")
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

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        architecture = plan.setdefault("architecture", {})
        attempt_counters = state.setdefault("attempt_counters", {})

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

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        request = plan.get("request") or _last_user_message(state)
        metadata = plan.setdefault("metadata", {})
        stack = metadata.get("stack", state.get("context", {}).get("stack", "LangGraph POC"))

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

    def __init__(self, template_path: str = "docs/implementation.md") -> None:
        self.template_path = Path(template_path)
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
            acceptance = [
                template_sections["checklist"],
                f"Scenario validation: {scenario_file}",
            ]
            phases.append(
                {
                    "name": name,
                    "owner": owner,
                    "deliverables": deliverables,
                    "acceptance": acceptance,
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
            f"- {p['name']} (owner: {p['owner']})" for p in phases
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
