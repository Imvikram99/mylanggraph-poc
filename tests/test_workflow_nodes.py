import src.graph.nodes.workflow as workflow_mod
import src.graph.nodes.langchain_agent as agent_mod
from src.graph.nodes.code_review import CodeReviewNode
from src.graph.nodes.langchain_agent import LangChainAgentNode
from src.graph.nodes.retry import RetryNode
from src.graph.nodes.summary import PlanSummaryNode
from src.graph.nodes.workflow import (
    ArchitecturePlannerNode,
    ImplementationPlannerNode,
    LeadPlannerNode,
    PlanReviewerNode,
    ProductOwnerNode,
    TechLeadNode,
    UiUxDesignerNode,
    WorkflowSelectorNode,
)
from src.graph.workflow_config import load_workflow_config


def base_state():
    return {
        "messages": [{"role": "user", "content": "Design a new feature request workflow"}],
        "context": {"persona": "architect", "mode": "architect", "stack": "LangGraph POC"},
    }


def test_workflow_nodes_generate_plan_end_to_end(monkeypatch):
    monkeypatch.setattr(workflow_mod, "request_codex", lambda *_, **__: "codex_ok")
    monkeypatch.setattr(workflow_mod, "request_gemini", lambda *_, **__: "gemini_ok")
    monkeypatch.setattr(agent_mod, "request_codex", lambda *_, **__: "codex_ok")
    monkeypatch.setattr(agent_mod, "run_sandboxed", lambda *_: "sandbox")
    config = load_workflow_config("configs/workflows.yaml")
    selector = WorkflowSelectorNode(config)
    product_owner = ProductOwnerNode(config)
    ui_ux_designer = UiUxDesignerNode(config)
    architect = ArchitecturePlannerNode(config)
    reviewer = PlanReviewerNode(config)
    lead_planner = LeadPlannerNode(config)
    tech = TechLeadNode(config)
    implementation = ImplementationPlannerNode(config)
    validator = workflow_mod.PlanValidatorNode()
    planner_summary = PlanSummaryNode()
    executor = LangChainAgentNode()
    reviewer_node = CodeReviewNode()

    state = base_state()
    selector.run(state)
    product_owner.run(state)
    ui_ux_designer.run(state)
    architect.run(state)
    RetryNode(reviewer.run, name="plan_reviewer", attempts=2, wait_seconds=0).run(state)
    lead_planner.run(state)
    tech.run(state)
    implementation.run(state)
    validator.run(state)
    planner_summary.run(state)
    executor.run(state)
    reviewer_node.run(state)

    assert state["plan"]["architecture"]["vision"]
    assert state["plan"]["architecture"]["api_design"]
    assert state["plan"]["phases"]
    assert state["workflow_phase"] in {"code_review", "execution"}
    assert "Phase 1" in state["output"]
