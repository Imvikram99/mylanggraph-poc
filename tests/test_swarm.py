from src.graph.nodes.swarm import SwarmNode


def test_swarm_emits_phase_summary():
    node = SwarmNode({"swarm": {"planner": "researcher", "workers": ["researcher", "writer"]}})
    state = {
        "messages": [{"role": "assistant", "content": "ready"}],
        "plan": {
            "phases": [
                {
                    "name": "Design Hardening",
                    "owner": "architect",
                    "deliverables": ["Document architecture"],
                    "acceptance": ["demo/feature_request.yaml"],
                }
            ]
        },
        "context": {"mode": "architect"},
    }
    result = node.run(state)
    assert "Design Hardening" in result["output"]
    assert "Deliverable" in result["output"]
