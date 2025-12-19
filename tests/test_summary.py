from src.graph.nodes.summary import ConversationSummaryNode


def test_summary_condenses_messages():
    node = ConversationSummaryNode(max_messages=4, keep_recent=2)
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(6)]
    state = {"messages": messages, "working_memory": {}, "metadata": {}}
    result = node.run(state)
    assert "conversation_summary" in result["working_memory"]
    assert result["messages"][0]["role"] == "system"
    assert len(result["messages"]) == 3
