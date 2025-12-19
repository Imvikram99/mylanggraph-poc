"""LangChain AgentExecutor node for autonomous workflows."""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console

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
        query = _last_user_content(state.get("messages", []))
        if not query:
            return state
        metadata = state.setdefault("metadata", {})
        if not self.available or self.agent is None:
            console.log("[yellow]LangChain unavailable; returning heuristic plan[/]")
            plan = self._fallback_plan(query)
            metadata["langchain_agent"] = {"iterations": len(plan)}
            state.setdefault("messages", []).append({"role": "assistant", "content": plan})
            state["output"] = plan
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


def _last_user_content(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""
