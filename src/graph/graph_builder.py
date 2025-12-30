"""LangGraph builder for the POC."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from langgraph.graph import END, START, StateGraph

from ..memory.temporal import TemporalMemoryStore
from ..observability.costs import CostLatencyTracker
from ..models.registry import load_policy_config
from .nodes import (
    ArchitecturePlannerNode,
    CodeReviewNode,
    ConversationSummaryNode,
    EvaluatorNode,
    GraphRAGNode,
    HandoffNode,
    HybridNode,
    ImplementationPlannerNode,
    LangChainAgentNode,
    MemoryRetrieveNode,
    MemoryWriteNode,
    PlanReviewerNode,
    PlanSummaryNode,
    RAGNode,
    RetryNode,
    RouterNode,
    SkillHubNode,
    SwarmNode,
    TechLeadNode,
    WorkflowSelectorNode,
)
from .state import FeatureState
from .workflow_config import load_workflow_config


def load_config(path: str | Path) -> Dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Graph config not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as fin:
        return yaml.safe_load(fin) or {}


def build_agent_graph(
    config_path: str | Path | None = None,
    checkpointer=None,
    monitor: CostLatencyTracker | None = None,
):
    """Build and compile the LangGraph agent."""
    resolved_config = config_path or os.getenv("GRAPH_CONFIG_PATH", "configs/graph_config.yaml")
    config = load_config(resolved_config)
    memory_store = TemporalMemoryStore()
    workflow_settings = config.get("workflows") or {}
    workflow_cfg_path = workflow_settings.get("config_path", "configs/workflows.yaml")
    implementation_doc = workflow_settings.get("implementation_doc", "docs/implementation.md")
    approvals_required = workflow_settings.get("require_approvals")
    if approvals_required is None:
        approvals_required = os.getenv("WORKFLOW_REQUIRE_APPROVALS", "false").lower() == "true"
    workflow_config = load_workflow_config(workflow_cfg_path)

    graph = StateGraph(FeatureState)
    policy_config = load_policy_config()
    router = RouterNode(config, policy_config=policy_config)
    rag = RAGNode()
    graphrag = GraphRAGNode()
    skills = SkillHubNode()
    handoff = HandoffNode(config)
    swarm = SwarmNode(config)
    memory_read = MemoryRetrieveNode(memory_store)
    memory_write = MemoryWriteNode(memory_store)
    summarizer = ConversationSummaryNode()
    evaluator = EvaluatorNode()
    langchain_agent = LangChainAgentNode()
    workflow_selector = WorkflowSelectorNode(workflow_config)
    architect = ArchitecturePlannerNode(workflow_config)
    plan_reviewer = PlanReviewerNode(workflow_config)
    tech_lead = TechLeadNode(workflow_config)
    implementation_planner = ImplementationPlannerNode(template_path=implementation_doc)
    plan_summary = PlanSummaryNode()
    code_reviewer = CodeReviewNode()

    rag_with_retry = RetryNode(rag.run, name="rag")
    graph_with_retry = RetryNode(graphrag.run, name="graph_rag", attempts=2)
    skills_with_retry = RetryNode(skills.run, name="skills", attempts=3, wait_seconds=1.0)
    hybrid = HybridNode(rag_with_retry.run, graph_with_retry.run)
    plan_reviewer_with_retry = RetryNode(plan_reviewer.run, name="plan_reviewer", attempts=2, wait_seconds=0.2)
    implementation_with_retry = RetryNode(implementation_planner.run, name="implementation_planner", attempts=2, wait_seconds=0.5)
    code_review_with_retry = RetryNode(code_reviewer.run, name="code_review", attempts=2, wait_seconds=0.5)

    wrap = monitor.wrap if monitor else (lambda name, fn: fn)

    graph.add_node("memory_retrieve", wrap("memory_retrieve", memory_read.run))
    graph.add_node("router", wrap("router", router.run))
    graph.add_node("conversation_summary", wrap("conversation_summary", summarizer.run))
    graph.add_node("rag", wrap("rag", rag_with_retry.run))
    graph.add_node("graph_rag", wrap("graph_rag", graph_with_retry.run))
    graph.add_node("hybrid", wrap("hybrid", hybrid.run))
    graph.add_node("skills", wrap("skills", skills_with_retry.run))
    graph.add_node("langchain_agent", wrap("langchain_agent", langchain_agent.run))
    graph.add_node("handoff", wrap("handoff", handoff.run))
    graph.add_node("swarm", wrap("swarm", swarm.run))
    graph.add_node("evaluator", wrap("evaluator", evaluator.run))
    graph.add_node("memory_write", wrap("memory_write", memory_write.run))
    graph.add_node("workflow_selector", wrap("workflow_selector", workflow_selector.run))
    graph.add_node("architecture_planner", wrap("architecture_planner", architect.run))
    graph.add_node("plan_reviewer", wrap("plan_reviewer", plan_reviewer_with_retry.run))
    graph.add_node("tech_lead", wrap("tech_lead", tech_lead.run))
    graph.add_node("implementation_planner", wrap("implementation_planner", implementation_with_retry.run))
    graph.add_node("plan_summary", wrap("plan_summary", plan_summary.run))
    graph.add_node("code_review", wrap("code_review", code_review_with_retry.run))

    graph.add_edge(START, "memory_retrieve")
    graph.add_edge("memory_retrieve", "conversation_summary")
    graph.add_edge("conversation_summary", "router")

    graph.add_conditional_edges(
        "router",
        router.branch,
        {
            "rag": "rag",
            "graph_rag": "graph_rag",
            "skills": "skills",
            "handoff": "handoff",
            "swarm": "swarm",
            "hybrid": "hybrid",
            "langchain_agent": "langchain_agent",
            "workflow": "workflow_selector",
        },
    )

    graph.add_edge("rag", "evaluator")
    graph.add_edge("skills", "evaluator")
    graph.add_edge("handoff", "swarm")
    graph.add_edge("swarm", "evaluator")
    graph.add_edge("hybrid", "evaluator")
    graph.add_edge("workflow_selector", "architecture_planner")
    graph.add_edge("architecture_planner", "plan_reviewer")
    graph.add_edge("plan_reviewer", "tech_lead")
    graph.add_edge("tech_lead", "implementation_planner")
    graph.add_edge("implementation_planner", "plan_summary")
    graph.add_edge("plan_summary", "langchain_agent")
    graph.add_edge("langchain_agent", "code_review")
    graph.add_edge("code_review", "evaluator")

    graph.add_conditional_edges(
        "graph_rag",
        graphrag.branch,
        {
            "ok": "evaluator",
            "fallback": "rag",
        },
    )
    graph.add_edge("evaluator", "memory_write")
    graph.add_edge("memory_write", END)

    interrupt_nodes = ["handoff", "swarm"]
    if approvals_required:
        interrupt_nodes.extend(["plan_reviewer", "tech_lead"])
    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_nodes)
