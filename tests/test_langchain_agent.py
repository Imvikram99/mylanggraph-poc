from src.graph.nodes.langchain_agent import LangChainAgentNode


def test_langchain_agent_returns_plan():
    node = LangChainAgentNode()
    state = {"messages": [{"role": "user", "content": "Analyze the system"}], "metadata": {}}
    result = node.run(state)
    assert "output" in result
    assert result["metadata"].get("langchain_agent") is not None
