from src.graph.nodes.skills import SkillHubNode


def test_skillhub_can_call_mcp_filesystem():
    node = SkillHubNode()
    state = {
        "messages": [{"role": "user", "content": "read file"}],
        "context": {
            "skill_pack": "mcp",
            "skill_tool": "filesystem_read",
            "skill_args": {"path": "memory_strategy.md"},
        },
    }
    result = node.run(state)
    assert "Memory Strategy" in result["output"]
    assert result["metadata"]["tools"][0]["tool"] == "filesystem_read"
