import importlib
from pathlib import Path

import skills.ops_pack.tools as ops_tools


def test_resolve_repo_workspace_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKFLOW_REPO_ROOT", str(tmp_path))
    reloaded = importlib.reload(ops_tools)
    repo_path = reloaded.resolve_repo_workspace(repo_url="https://github.com/example/project.git")
    assert repo_path == Path(tmp_path) / "project"


def test_prepare_repo_handles_existing_repo(monkeypatch, tmp_path):
    repo_dir = tmp_path / "custom"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    monkeypatch.setattr(ops_tools, "run_sandboxed", lambda command: f"ran:{command}")
    result = ops_tools.prepare_repo(repo_path=str(repo_dir), branch="feature/test", feature="demo")
    assert "ran:" in result
    assert "feature/test" in result
