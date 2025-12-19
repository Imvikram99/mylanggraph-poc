from src.graph.nodes.rag import RAGNode


def test_rag_retrieves_from_filesystem(monkeypatch):
    monkeypatch.setenv("VECTOR_DB_IMPL", "files")
    node = RAGNode()
    state = {"messages": [{"role": "user", "content": "Explain LangGraph memory strategy"}]}
    result = node.run(state)
    assert "Memory Strategy" in result["output"]
    assert result.get("artifacts")
