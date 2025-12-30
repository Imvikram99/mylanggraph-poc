"""Bridge LangGraph workflow requests to the Codex CLI."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from shlex import split
from typing import Optional

import typer

LOG_PATH = Path("data/ops/codex_requests.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

app = typer.Typer(help="Relay workflow instructions to the Codex CLI.")


def dispatch(
    instruction: str,
    repo_path: Optional[str] = None,
    branch: Optional[str] = None,
    *,
    dry_run: bool = False,
) -> str:
    """Invoke the Codex CLI with the provided instruction."""
    instruction = (instruction or "").strip()
    if not instruction:
        return "[codex_proxy] No instruction supplied."
    resolved_repo = Path(repo_path).expanduser() if repo_path else None
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "instruction": instruction,
        "repo_path": str(resolved_repo) if resolved_repo else None,
        "branch": branch,
    }
    _append_log(payload)
    cli_cmd = os.getenv("CODEX_CLI_COMMAND") or os.getenv("CODEX_CLI_BIN")
    if not cli_cmd:
        return f"[codex_proxy] Set CODEX_CLI_COMMAND to forward requests. Logged to {LOG_PATH}."
    formatted = _format_instruction(payload)
    env = os.environ.copy()
    if resolved_repo:
        env.setdefault("CODEX_TARGET_REPO", str(resolved_repo))
    if branch:
        env.setdefault("CODEX_TARGET_BRANCH", branch)
    timeout_s = int(os.getenv("CODEX_CLI_TIMEOUT", "600"))
    if dry_run:
        return f"[codex_proxy] Dry-run: would run '{cli_cmd}' with instruction logged at {LOG_PATH}."
    try:
        proc = subprocess.run(
            split(cli_cmd),
            input=formatted,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env=env,
            check=False,
        )
    except FileNotFoundError:
        return f"[codex_proxy] CLI command '{cli_cmd}' not found. Logged to {LOG_PATH}."
    except subprocess.SubprocessError as exc:
        return f"[codex_proxy] CLI error: {exc}"
    summary = _summarize_process(proc)
    return f"[codex_proxy] {summary}"


@app.command()
def run(
    instruction: str = typer.Argument(..., help="Instruction payload for Codex CLI."),
    repo: Optional[Path] = typer.Option(None, "--repo", help="Repository path"),
    branch: Optional[str] = typer.Option(None, "--branch", help="Target Git branch."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip calling CLI, log only."),
    cli_command: Optional[str] = typer.Option(None, "--cli-command", help="Command used to invoke Codex CLI."),
):
    if cli_command:
        os.environ["CODEX_CLI_COMMAND"] = cli_command
    typer.echo(dispatch(instruction, repo_path=str(repo) if repo else None, branch=branch, dry_run=dry_run))


def _append_log(entry: dict) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as fout:
        fout.write(json.dumps(entry) + "\n")


def _format_instruction(payload: dict) -> str:
    lines = [
        "# Codex CLI Task",
        f"Repository: {payload.get('repo_path') or 'unspecified'}",
        f"Branch: {payload.get('branch') or 'current'}",
        "Instruction:",
        payload["instruction"],
        "",
    ]
    return "\n".join(lines)


def _summarize_process(proc: subprocess.CompletedProcess) -> str:
    parts = [f"exit={proc.returncode}"]
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if stdout:
        parts.append(f"stdout={stdout[:160]}")
    if stderr:
        parts.append(f"stderr={stderr[:160]}")
    return " ".join(parts)


if __name__ == "__main__":
    app()
