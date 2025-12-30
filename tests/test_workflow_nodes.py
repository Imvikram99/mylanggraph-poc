from src.graph.nodes.code_review import CodeReviewNode
from src.graph.nodes.langchain_agent import LangChainAgentNode
from src.graph.nodes.retry import RetryNode
from src.graph.nodes.summary import PlanSummaryNode
from src.graph.nodes.workflow import (
    ArchitecturePlannerNode,
    ImplementationPlannerNode,
    PlanReviewerNode,
    TechLeadNode,
    WorkflowSelectorNode,
)
from src.graph.workflow_config import load_workflow_config


def base_state():
    return {
        "messages": [{"role": "user", "content": "Design a new feature request workflow"}],
        "context": {"persona": "architect", "mode": "architect", "stack": "LangGraph POC"},
    }


def test_workflow_nodes_generate_plan_end_to_end():
    config = load_workflow_config("configs/workflows.yaml")
    selector = WorkflowSelectorNode(config)
    architect = ArchitecturePlannerNode(config)
    reviewer = PlanReviewerNode(config)
    tech = TechLeadNode(config)
    implementation = ImplementationPlannerNode()
    planner_summary = PlanSummaryNode()
    executor = LangChainAgentNode()
    reviewer_node = CodeReviewNode()

    state = base_state()
    selector.run(state)
    architect.run(state)
    RetryNode(reviewer.run, name="plan_reviewer", attempts=2, wait_seconds=0).run(state)
    tech.run(state)
    implementation.run(state)
    planner_summary.run(state)
    executor.run(state)
    reviewer_node.run(state)

    assert state["plan"]["architecture"]["vision"]
    assert state["plan"]["phases"]
    assert state["workflow_phase"] in {"code_review", "execution"}
    assert "Phase 1" in state["output"]
