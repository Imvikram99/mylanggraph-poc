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
    ConversationSummaryNode,
    EvaluatorNode,
    GraphRAGNode,
    HandoffNode,
    HybridNode,
    LangChainAgentNode,
    MemoryRetrieveNode,
    MemoryWriteNode,
    RAGNode,
    RetryNode,
    RouterNode,
    SkillHubNode,
    SwarmNode,
)
from .state import AgentState


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

    graph = StateGraph(AgentState)
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

    rag_with_retry = RetryNode(rag.run, name="rag")
    graph_with_retry = RetryNode(graphrag.run, name="graph_rag", attempts=2)
    skills_with_retry = RetryNode(skills.run, name="skills", attempts=3, wait_seconds=1.0)
    hybrid = HybridNode(rag_with_retry.run, graph_with_retry.run)

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
        },
    )

    graph.add_edge("rag", "evaluator")
    graph.add_edge("skills", "evaluator")
    graph.add_edge("langchain_agent", "evaluator")
    graph.add_edge("handoff", "swarm")
    graph.add_edge("swarm", "evaluator")
    graph.add_edge("hybrid", "evaluator")

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
    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_nodes)
