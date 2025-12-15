"""LangGraph builder for the POC."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, TypedDict

import yaml
from langgraph.graph import END, START, StateGraph

from ..memory.temporal import TemporalMemoryStore
from .nodes import (
    GraphRAGNode,
    HandoffNode,
    MemoryRetrieveNode,
    MemoryWriteNode,
    RAGNode,
    RouterNode,
    SkillHubNode,
    SwarmNode,
)


class AgentState(TypedDict, total=False):
    """LangGraph agent state contract."""

    messages: List[Dict[str, Any]]
    working_memory: Dict[str, Any]
    metadata: Dict[str, Any]
    artifacts: List[str]
    route: str
    context: Dict[str, Any]
    output: str


def load_config(path: str | Path) -> Dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Graph config not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as fin:
        return yaml.safe_load(fin) or {}


def build_agent_graph(
    config_path: str = "configs/graph_config.yaml",
    checkpointer=None,
):
    """Build and compile the LangGraph agent."""
    config = load_config(config_path)
    memory_store = TemporalMemoryStore()

    graph = StateGraph(AgentState)
    router = RouterNode(config)
    rag = RAGNode()
    graphrag = GraphRAGNode()
    skills = SkillHubNode()
    handoff = HandoffNode(config)
    swarm = SwarmNode(config)
    memory_read = MemoryRetrieveNode(memory_store)
    memory_write = MemoryWriteNode(memory_store)

    graph.add_node("memory_retrieve", memory_read.run)
    graph.add_node("router", router.run)
    graph.add_node("rag", rag.run)
    graph.add_node("graph_rag", graphrag.run)
    graph.add_node("skills", skills.run)
    graph.add_node("handoff", handoff.run)
    graph.add_node("swarm", swarm.run)
    graph.add_node("memory_write", memory_write.run)

    graph.add_edge(START, "memory_retrieve")
    graph.add_edge("memory_retrieve", "router")

    graph.add_conditional_edges(
        "router",
        router.branch,
        {
            "rag": "rag",
            "graph_rag": "graph_rag",
            "skills": "skills",
            "handoff": "handoff",
            "swarm": "swarm",
        },
    )

    graph.add_edge("rag", "memory_write")
    graph.add_edge("graph_rag", "memory_write")
    graph.add_edge("skills", "memory_write")
    graph.add_edge("handoff", "swarm")
    graph.add_edge("swarm", "memory_write")
    graph.add_edge("memory_write", END)

    return graph.compile(checkpointer=checkpointer)
