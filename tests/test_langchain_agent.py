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
                    "owners": ["architect"],
                    "deliverables": ["Document architecture"],
                    "acceptance_tests": ["Scenario validation: demo/feature_request.yaml"],
                }
            ]
        },
        "messages": [{"role": "user", "content": "start"}],
        "metadata": {},
    }
    result = node.run(state)
    assert "Design Hardening" in result["output"]
    assert result["workflow_phase"] == "execution"


def test_langchain_agent_session_init_calls_share_session(monkeypatch):
    calls = []

    def _capture_request(instruction, **kwargs):
        calls.append({"instruction": instruction, "kwargs": kwargs})
        return "codex_ok"

    monkeypatch.setattr(agent_mod, "request_codex", _capture_request)
    monkeypatch.setattr(agent_mod, "run_sandboxed", lambda *_: "sandbox")
    config = {"roles": {"architect": {"prompt": "Act as an architect."}}}
    node = agent_mod.LangChainAgentNode(workflow_config=config)
    state = {
        "plan": {
            "request": "Ship feature",
            "phases": [
                {
                    "name": "Design Hardening",
                    "owners": ["architect"],
                    "deliverables": ["Document architecture"],
                    "acceptance_tests": ["Scenario validation: demo/feature_request.yaml"],
                }
            ],
        },
        "messages": [{"role": "user", "content": "start"}],
        "metadata": {},
    }
    node.run(state)
    assert len(calls) == 2
    assert calls[0]["instruction"].startswith("Session init.")
    assert "Feature request: Ship feature" in calls[1]["instruction"]
    session_ids = {call["kwargs"].get("session_id") for call in calls}
    session_names = {call["kwargs"].get("session_name") for call in calls}
    phases = {call["kwargs"].get("phase") for call in calls}
    assert session_ids and None not in session_ids and len(session_ids) == 1
    assert session_names and None not in session_names and len(session_names) == 1
    assert phases == {"Design Hardening"}


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
                {
                    "name": "Phase Alpha",
                    "owners": ["architect"],
                    "deliverables": ["Do X"],
                    "acceptance_tests": ["Test Y"],
                },
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


def test_langchain_agent_plan_only_skips_execution(monkeypatch):
    called = {"count": 0}

    def _raise_if_called(*_, **__):
        called["count"] += 1
        return "should_not_run"

    monkeypatch.setattr(agent_mod, "request_codex", _raise_if_called)
    node = agent_mod.LangChainAgentNode()
    state = {
        "plan": {
            "phases": [
                {
                    "name": "Phase Alpha",
                    "owners": ["architect"],
                    "deliverables": ["Do X"],
                    "acceptance_tests": ["Test Y"],
                },
            ],
            "summary": "Planning complete",
        },
        "context": {"plan_only": True},
        "metadata": {},
    }
    result = node.run(state)
    assert called["count"] == 0
    assert result["workflow_phase"] == "plan_only"
    assert "Planning complete" in result["output"]
    phase_exec = result["metadata"]["phase_execution"]
    assert phase_exec["skipped"] == "plan_only"
