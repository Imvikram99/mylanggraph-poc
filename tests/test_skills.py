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


def test_skillhub_reads_architecture_note_from_kb():
    node = SkillHubNode()
    state = {
        "messages": [{"role": "user", "content": "architecture brief"}],
        "context": {
            "skill_pack": "mcp",
            "skill_tool": "filesystem_read",
            "skill_args": {"path": "architecture/module_responsibilities.md"},
        },
    }
    result = node.run(state)
    assert "LangGraph Module Responsibilities" in result["output"]
    assert "Router Node" in result["output"]
