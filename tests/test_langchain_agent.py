from src.graph.nodes.langchain_agent import LangChainAgentNode


def test_langchain_agent_returns_plan():
    node = LangChainAgentNode()
    state = {"messages": [{"role": "user", "content": "Analyze the system"}], "metadata": {}}
    result = node.run(state)
    assert "output" in result
    assert result["metadata"].get("langchain_agent") is not None


def test_langchain_agent_handles_phases():
    node = LangChainAgentNode()
    state = {
        "plan": {
            "phases": [
                {
                    "name": "Design Hardening",
                    "owner": "architect",
                    "deliverables": ["Document architecture"],
                    "acceptance": ["Scenario validation: demo/feature_request.yaml"],
                }
            ]
        },
        "messages": [{"role": "user", "content": "start"}],
        "metadata": {},
    }
    result = node.run(state)
    assert "Design Hardening" in result["output"]
    assert result["workflow_phase"] == "execution"
