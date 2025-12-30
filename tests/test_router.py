from src.graph.nodes.router import RouterNode


def make_state(prompt: str, **context):
    return {
        "messages": [{"role": "user", "content": prompt}],
        "context": context,
        "metadata": {"agent": context.get("persona", "researcher")},
    }


def test_router_respects_force_route():
    router = RouterNode({})
    state = make_state("Please write", force_route="skills")
    router.run(state)
    assert state["route"] == "skills"
    assert state["metadata"]["router_reason"] == "forced_by_context"


def test_router_prefers_graph_for_relationship_queries():
    router = RouterNode({})
    state = make_state("Map the relationship graph between teams")
    router.run(state)
    assert state["route"] == "graph_rag"


def test_router_uses_swarm_for_complex_tasks():
    router = RouterNode({})
    state = make_state(
        "Plan and coordinate a multi-step delivery",
        task_complexity="high",
        latency_budget_s=30,
    )
    router.run(state)
    assert state["route"] == "swarm"


def test_router_can_force_hybrid_mode():
    router = RouterNode({})
    state = make_state(
        "Compare and analyze the relationships between research teams and ops staff",
        mode="hybrid",
    )
    router.run(state)
    assert state["route"] == "hybrid"


def test_router_detects_feature_workflow():
    router = RouterNode({})
    state = make_state(
        "I need an architecture plan for a new feature request",
        mode="architect",
    )
    router.run(state)
    assert state["route"] == "workflow"
    assert state["metadata"]["router_reason"] == "workflow_request"
