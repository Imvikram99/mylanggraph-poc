from pathlib import Path

import src.graph.nodes.langchain_agent as agent_mod


def test_langchain_agent_returns_plan():
    node = agent_mod.LangChainAgentNode()
    state = {"messages": [{"role": "user", "content": "Analyze the system"}], "metadata": {}}
    result = node.run(state)
    assert "output" in result
    assert result["metadata"].get("langchain_agent") is not None


def test_langchain_agent_handles_phases(monkeypatch):
    monkeypatch.setattr(agent_mod, "request_codex", lambda *_, **__: "codex_ok")
    node = agent_mod.LangChainAgentNode()
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


def test_langchain_agent_with_repo_context(monkeypatch):
    monkeypatch.setattr(agent_mod, "prepare_repo", lambda **_: "prepared repo")
    monkeypatch.setattr(agent_mod, "resolve_repo_workspace", lambda **_: Path("/tmp/workspace"))
    monkeypatch.setattr(agent_mod, "run_repo_command", lambda *_, **__: "[sandbox] exit=0 output=git status")
    monkeypatch.setattr(agent_mod, "run_sandboxed", lambda command: f"fallback:{command}")
    monkeypatch.setattr(agent_mod, "request_codex", lambda *_, **__: "codex_ok_repo")
    node = agent_mod.LangChainAgentNode()
    state = {
        "plan": {
            "phases": [
                {"name": "Phase Alpha", "deliverables": ["Do X"], "acceptance": ["Test Y"]},
            ]
        },
        "messages": [{"role": "user", "content": "build"}],
        "metadata": {},
        "context": {"repo_path": "/tmp/workspace", "target_branch": "feature/test"},
    }
    result = node.run(state)
    assert "Repo command" in result["output"]
    assert result["metadata"]["phase_execution"]["repo_path"] == "/tmp/workspace"
    codex_calls = result["metadata"]["phase_execution"]["codex_calls"]
    assert codex_calls and codex_calls[0]["result"] == "codex_ok_repo"
