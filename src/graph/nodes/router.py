"""Router node selecting downstream path."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Dict, Optional

from rich.console import Console

from ..state import RouteDecision
from ...models.policy import ModelPolicy

console = Console()


class RouterNode:
    """Heuristic router that chooses between RAG, GraphRAG, skills, or swarm."""

    DEFAULT_THRESHOLDS = {
        "graph_rag": 0.45,
        "skills": 0.4,
        "handoff": 0.35,
        "swarm": 0.5,
        "langchain_agent": 0.5,
        "workflow": 0.5,
    }

    def __init__(self, config: Dict[str, Any], policy_config: Dict[str, Any] | None = None) -> None:
        self.config = config or {}
        router_cfg = (self.config.get("defaults", {}) or {}).get("router", {})
        thresholds = router_cfg.get("thresholds", {})
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **thresholds}
        self.graph_latency_cutoff = float(router_cfg.get("graph_min_latency", 6))
        self.swarm_complexity = router_cfg.get("swarm_complexity_keyword", "high")
        self.policy = ModelPolicy(policy_config)

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        decision = self.decide_route(state)
        metadata = state.setdefault("metadata", {})
        metadata.setdefault("route_history", []).append(decision.route)
        metadata["router_reason"] = decision.reason
        metadata["router_scores"] = decision.scores
        metadata["router_decision"] = asdict(decision)
        state["route"] = decision.route
        console.log(f"[bold]Router[/] selected route={decision.route} ({decision.reason})")
        return state

    def decide_route(self, state: Dict[str, Any]) -> RouteDecision:
        context = state.get("context", {})
        disabled = set(context.get("disable_routes", []))
        scores: Dict[str, float] = {}
        policy_hint = self.policy.advise(context)

        forced = context.get("force_route") or policy_hint.get("force_route")
        disabled.update(policy_hint.get("disable_routes", []))

        if forced and forced not in disabled:
            return RouteDecision(route=forced, reason="forced_by_context", scores=scores)

        latency_budget = float(context.get("latency_budget_s", 0) or 0)
        cost_budget = float(context.get("cost_budget_usd", 0) or 0)
        telemetry = (state.get("metadata") or {}).get("telemetry", {})
        elapsed_latency = float(telemetry.get("latency_s") or 0)
        spent_cost = float(telemetry.get("cost_estimate_usd") or 0)
        if latency_budget and elapsed_latency >= latency_budget:
            disabled.update({"graph_rag", "swarm", "hybrid"})
        if cost_budget and spent_cost >= cost_budget:
            disabled.update({"swarm", "langchain_agent", "hybrid"})
        last_message = _last_message(state)

        scores["graph_rag"] = self._score_graph(last_message, context, latency_budget, elapsed_latency)
        scores["skills"] = self._score_skills(last_message, context)
        scores["handoff"] = self._score_handoff(state, context)
        scores["swarm"] = self._score_swarm(last_message, context, latency_budget, cost_budget, elapsed_latency, spent_cost)
        scores["langchain_agent"] = self._score_langchain_agent(last_message, context, cost_budget, spent_cost)
        scores["workflow"] = self._score_workflow(last_message, context)

        if self._should_use_hybrid(last_message, context, scores, disabled):
            scores["hybrid"] = 1.0
            return RouteDecision(route="hybrid", reason="graph+rag_combo", scores=scores)

        preferred = policy_hint.get("preferred_route")
        if preferred:
            scores[preferred] = min(1.0, scores.get(preferred, 0.0) + float(policy_hint.get("boost", 0.15)))

        for route, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
            if route in disabled:
                continue
            if score >= self.thresholds.get(route, 0.3):
                reason = f"score={score:.2f}"
                if route == preferred:
                    reason = f"{reason};policy={policy_hint.get('name')}"
                if route == "workflow":
                    reason = "workflow_request"
                return RouteDecision(route=route, reason=reason, scores=scores)
        return RouteDecision(route="rag", reason="default_fallback", scores=scores)

    def branch(self, state: Dict[str, Any]) -> str:
        return state.get("route", "rag")

    # --------------------- scoring helpers ---------------------
    def _score_graph(self, message: str, context: Dict[str, Any], latency_budget: float, elapsed_latency: float) -> float:
        score = 0.0
        if context.get("requires_graph"):
            score += 0.6
        if re.search(r"\bgraph\b|\brelationship\b|\bnetwork\b", message, re.IGNORECASE):
            score += 0.3
        if re.search(r"\bgraph\b", message, re.IGNORECASE) and re.search(r"\brelationship\b", message, re.IGNORECASE):
            score += 0.2
        if len(message.split()) > 40:
            score += 0.1
        if latency_budget and latency_budget < self.graph_latency_cutoff:
            score *= 0.5
        if latency_budget and elapsed_latency:
            ratio = elapsed_latency / latency_budget
            if ratio >= 1.0:
                return 0.0
            if ratio >= 0.6:
                score *= 0.4
        return min(score, 1.0)

    def _score_skills(self, message: str, context: Dict[str, Any]) -> float:
        score = 0.0
        if context.get("skill_pack"):
            score += 0.5
        if re.search(r"\b(write|outline|draft|summarize)\b", message, re.IGNORECASE):
            score += 0.3
        if context.get("skill_tool"):
            score += 0.2
        return min(score, 1.0)

    def _score_handoff(self, state: Dict[str, Any], context: Dict[str, Any]) -> float:
        current_agent = (state.get("metadata") or {}).get("agent", "researcher")
        target_agent = context.get("persona")
        if target_agent and target_agent != current_agent:
            return 0.6
        if "handoff" in (_last_message(state) or "").lower():
            return 0.4
        return 0.0

    def _score_swarm(
        self,
        message: str,
        context: Dict[str, Any],
        latency_budget: float,
        cost_budget: float,
        elapsed_latency: float,
        spent_cost: float,
    ) -> float:
        score = 0.0
        complexity = str(context.get("task_complexity", "")).lower()
        if complexity == self.swarm_complexity:
            score += 0.5
        if re.search(r"\b(plan|coordinate|multi-step)\b", message, re.IGNORECASE):
            score += 0.3
        if len(message.split()) > 80:
            score += 0.1
        if latency_budget and latency_budget < 10:
            score *= 0.7
        if latency_budget and elapsed_latency > latency_budget * 0.7:
            score *= 0.5
        if cost_budget and (cost_budget < 0.25 or spent_cost > cost_budget * 0.8):
            score *= 0.6
        return min(score, 1.0)

    def _score_langchain_agent(
        self,
        message: str,
        context: Dict[str, Any],
        cost_budget: float,
        spent_cost: float,
    ) -> float:
        score = 0.0
        if context.get("mode") == "agentic":
            score += 0.7
        if re.search(r"\bautonomous\b|\bagentic\b|\bworkflow\b", message, re.IGNORECASE):
            score += 0.3
        if context.get("require_langchain"):
            score = 1.0
        if cost_budget and spent_cost > cost_budget * 0.9:
            score *= 0.4
        return min(score, 1.0)

    def _should_use_hybrid(
        self,
        message: str,
        context: Dict[str, Any],
        scores: Dict[str, float],
        disabled: set[str],
    ) -> bool:
        if "hybrid" in disabled or not context.get("allow_hybrid", True):
            return False
        if context.get("mode") == "hybrid":
            return True
        graph_score = scores.get("graph_rag", 0.0)
        if graph_score < self.thresholds.get("graph_rag", 0.45):
            return False
        if len(message.split()) > 60 and re.search(r"\b(compare|analyze|relationship)\b", message, re.IGNORECASE):
            return True
        return False

    def _score_workflow(self, message: str, context: Dict[str, Any]) -> float:
        score = 0.0
        mode = context.get("mode")
        if mode == "architect":
            return 1.0
        if context.get("workflow_intent"):
            score += 0.6
        if re.search(r"\b(feature request|workflow plan|tech lead)\b", message, re.IGNORECASE):
            score += 0.4
        if "architect" in str(context.get("persona", "")).lower():
            score += 0.2
        return min(score, 1.0)


def _last_message(state: Dict[str, Any]) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    return str(messages[-1].get("content", ""))
