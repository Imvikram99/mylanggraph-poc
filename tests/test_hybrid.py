from src.graph.nodes.hybrid import HybridNode


def test_hybrid_merges_rag_and_graph_outputs():
    def rag_runner(state):
        state.setdefault("messages", []).append({"role": "assistant", "content": "RAG content"})
        state["output"] = "RAG content"
        return state

    def graph_runner(state):
        state.setdefault("messages", []).append({"role": "assistant", "content": "Graph content"})
        state["output"] = "Graph content"
        return state

    node = HybridNode(rag_runner, graph_runner)
    state = {"messages": [{"role": "user", "content": "Explain"}]}
    result = node.run(state)
    assert "RAG insight" in result["output"]
    assert "Graph insight" in result["output"]
    assert result["messages"][-1]["content"] == result["output"]
