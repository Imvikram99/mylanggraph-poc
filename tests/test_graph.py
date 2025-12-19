from src.graph.nodes.graph_rag import GraphRAGNode


def test_graph_rag_uses_entity_graph():
    node = GraphRAGNode()
    state = {
        "messages": [
            {
                "role": "user",
                "content": "Explain how Research Agent collaborates with Writer Agent",
            }
        ]
    }
    result = node.run(state)
    assert "Research Agent" in result["output"]
    assert "Writer Agent" in result["output"]
