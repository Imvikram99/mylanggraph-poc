"""Ops pack tools with simple persistence for tickets and repo automation."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from shlex import quote
from typing import Dict, Optional

_DATA_DIR = Path("data/ops")
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_TICKETS_FILE = _DATA_DIR / "tickets.jsonl"


def file_ticket(summary: str, severity: str = "medium", owner: str = "ops") -> str:
    """Persist a ticket request locally to simulate creating an external ticket."""
    ticket = _build_ticket(summary, severity, owner)
    with _TICKETS_FILE.open("a", encoding="utf-8") as fout:
        fout.write(json.dumps(ticket) + "\n")
    return f"Queued ticket #{ticket['id']} for {summary[:48]} (severity={severity})."


def run_sandboxed(command: str) -> str:
    """Execute a shell command via a lightweight sandbox shim (placeholder)."""
    if not command.strip():
        return "No command provided to sandbox."
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - defensive path
        return f"[sandbox] failed to execute '{command}': {exc}"
    output = result.stdout.strip() or result.stderr.strip() or "(no output)"
    return f"[sandbox] exit={result.returncode} output={output[:400]}"


def prepare_repo(
    repo_path: Optional[str] = None,
    repo_url: Optional[str] = None,
    branch: Optional[str] = None,
    feature: Optional[str] = None,
) -> str:
    """Ensure a repository exists locally and optionally checkout a branch."""
    resolved = _resolve_repo_path(repo_path, repo_url)
    logs = []
    if not resolved.exists():
        resolved.parent.mkdir(parents=True, exist_ok=True)
        if repo_url:
            logs.append(run_sandboxed(f"git clone {repo_url} {quote(str(resolved))}"))
        else:
            resolved.mkdir(parents=True, exist_ok=True)
            logs.append(f"Initialized empty workspace at {resolved}")
    else:
        logs.append(f"Using existing repo at {resolved}")
    git_dir = resolved / ".git"
    if branch:
        if git_dir.exists():
            checkout_cmd = f"git checkout {branch} || git checkout -b {branch}"
            logs.append(run_repo_command(resolved, checkout_cmd))
        else:
            logs.append(f"Skipping checkout: {resolved} is not a git repo yet (branch={branch}).")
    if feature:
        logs.append(f"Feature context: {feature}")
    return "\n".join(logs)


def run_repo_command(repo_path: str | Path, command: str) -> str:
    """Execute a shell command inside the given repository path."""
    resolved = Path(repo_path).expanduser()
    if not resolved.exists():
        return f"[sandbox] repo path {resolved} missing; skipped '{command}'"
    return run_sandboxed(f"cd {quote(str(resolved))} && {command}")


def _build_ticket(summary: str, severity: str, owner: str) -> Dict[str, str]:
    timestamp = datetime.now(timezone.utc).isoformat()
    ticket_id = f"OPS-{int(datetime.now(timezone.utc).timestamp())}"
    return {
        "id": ticket_id,
        "summary": summary,
        "severity": severity,
        "owner": owner,
        "ts": timestamp,
    }


def resolve_repo_workspace(repo_path: Optional[str] = None, repo_url: Optional[str] = None) -> Path:
    """Return the workspace path for a repository input (ensures base directory exists)."""
    return _resolve_repo_path(repo_path, repo_url)


def _resolve_repo_path(repo_path: Optional[str], repo_url: Optional[str]) -> Path:
    if repo_path:
        return Path(repo_path).expanduser()
    if repo_url:
        slug = repo_url.rstrip("/").split("/")[-1]
        if slug.endswith(".git"):
            slug = slug[:-4]
        slug = slug or "repo"
    else:
        slug = "repo"
    return _workspace_root() / slug


def _workspace_root() -> Path:
    root = Path(os.getenv("WORKFLOW_REPO_ROOT", "data/workspaces")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root
