"""Conversation summarizer node to keep short-term memory manageable."""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console

from ..messages import append_message

console = Console()


class ConversationSummaryNode:
    """Produces lightweight summaries when the message buffer exceeds a threshold."""

    def __init__(self, *, max_messages: int = 20, keep_recent: int = 6) -> None:
        self.max_messages = max_messages
        self.keep_recent = keep_recent

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        messages = state.get("messages", [])
        if len(messages) <= self.max_messages:
            return state
        summary = self._summarize(messages)
        working = state.setdefault("working_memory", {})
        working["conversation_summary"] = summary

        recent = messages[-self.keep_recent :]
        state["messages"] = [{"role": "system", "content": summary}] + recent
        history = state.setdefault("metadata", {}).setdefault("summaries", [])
        history.append(summary)
        console.log(f"[green]Conversation summary[/] compressed {len(messages)} messages")
        return state

    def _summarize(self, messages: List[Dict[str, Any]]) -> str:
        last_user = next((msg["content"] for msg in reversed(messages) if msg.get("role") == "user"), "")
        last_assistant = next((msg["content"] for msg in reversed(messages) if msg.get("role") == "assistant"), "")
        snippet_user = _truncate(last_user)
        snippet_assistant = _truncate(last_assistant)
        return f"Recent exchange — user: {snippet_user}; assistant: {snippet_assistant}"


def _truncate(text: Any, limit: int = 120) -> str:
    value = str(text)
    return value[:limit] + ("…" if len(value) > limit else "")


class PlanSummaryNode:
    """Condense architect/reviewer chatter into a concise brief before coding."""

    def __init__(self, *, max_length: int = 800) -> None:
        self.max_length = max_length

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.setdefault("plan", {})
        summary_lines = []
        request = plan.get("request")
        architecture = plan.get("architecture") or {}
        implementation = plan.get("implementation") or {}
        phases = plan.get("phases") or []
        if request:
            summary_lines.append(f"Feature request: {request}")
        if architecture.get("vision"):
            summary_lines.append(f"Architecture vision: {architecture['vision']}")
        if architecture.get("guardrails"):
            summary_lines.append(f"Guardrails: {architecture['guardrails']}")
        if implementation.get("stack_recommendation"):
            summary_lines.append(f"Stack guidance: {implementation['stack_recommendation']}")
        if phases:
            names = ", ".join(phase.get("name", f"Phase {idx+1}") for idx, phase in enumerate(phases))
            summary_lines.append(f"Planned phases: {names}")
        brief = " ".join(summary_lines)[: self.max_length]
        if not brief:
            return state
        plan["summary"] = brief
        append_message(state, "system", f"Implementation brief: {brief}")
        state["workflow_phase"] = "plan_summary"
        state.setdefault("checkpoints", []).append({"phase": "plan_summary", "summary": brief})
        console.log("[green]PlanSummary[/] emitted condensed brief")
        return state
