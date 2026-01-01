"""Bridge LangGraph workflow requests to the Gemini Code CLI."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from shlex import split
from typing import Optional

import typer

LOG_PATH = Path("data/ops/gemini_requests.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
PROMPT_LOG_PATH = Path("docs/gemini_prompts.md")
PROMPT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

app = typer.Typer(help="Relay workflow instructions to the Gemini Code CLI.")


@app.callback()
def main():
    """Relay workflow instructions to the Gemini Code CLI."""


def dispatch(
    instruction: str,
    repo_path: Optional[str] = None,
    branch: Optional[str] = None,
    session_id: Optional[str] = None,
    session_name: Optional[str] = None,
    phase: Optional[str] = None,
    *,
    dry_run: bool = False,
) -> str:
    """Invoke the Gemini Code CLI with the provided instruction."""
    instruction = (instruction or "").strip()
    if not instruction:
        return "[gemini_proxy] No instruction supplied."
    resolved_repo = Path(repo_path).expanduser() if repo_path else None
    cli_cmd = os.getenv("GEMINI_CLI_COMMAND") or os.getenv("GEMINI_CLI_BIN") or "gemini"
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "instruction": instruction,
        "repo_path": str(resolved_repo) if resolved_repo else None,
        "branch": branch,
        "phase": phase,
        "session_id": session_id,
        "session_name": session_name,
        "cli_command": cli_cmd,
    }
    _append_log(payload)
    _append_prompt_markdown(payload)
    formatted = _format_instruction(payload)
    env = os.environ.copy()
    if resolved_repo:
        env.setdefault("GEMINI_TARGET_REPO", str(resolved_repo))
    if branch:
        env.setdefault("GEMINI_TARGET_BRANCH", branch)
    timeout_s = int(os.getenv("GEMINI_CLI_TIMEOUT", "600"))
    if dry_run:
        return f"[gemini_proxy] Dry-run: would run '{cli_cmd}' with instruction logged at {LOG_PATH}."
    try:
        cmd = split(cli_cmd)
        cmd.append(formatted)
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env=env,
            check=False,
            cwd=str(resolved_repo) if resolved_repo else None,
        )
    except FileNotFoundError:
        return f"[gemini_proxy] CLI command '{cli_cmd}' not found. Logged to {LOG_PATH}."
    except subprocess.SubprocessError as exc:
        return f"[gemini_proxy] CLI error: {exc}"
    summary = _summarize_process(proc)
    return f"[gemini_proxy] {summary}"


@app.command()
def run(
    instruction: str = typer.Argument(..., help="Instruction payload for Gemini CLI."),
    repo: Optional[Path] = typer.Option(None, "--repo", help="Repository path"),
    branch: Optional[str] = typer.Option(None, "--branch", help="Target Git branch."),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Session identifier for Gemini CLI."),
    session_name: Optional[str] = typer.Option(None, "--session-name", help="Session label for Gemini CLI."),
    phase: Optional[str] = typer.Option(None, "--phase", help="Workflow phase for the Gemini request."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip calling CLI, log only."),
    cli_command: Optional[str] = typer.Option(None, "--cli-command", help="Command used to invoke Gemini CLI."),
):
    if cli_command:
        os.environ["GEMINI_CLI_COMMAND"] = cli_command
    typer.echo(
        dispatch(
            instruction,
            repo_path=str(repo) if repo else None,
            branch=branch,
            session_id=session_id,
            session_name=session_name,
            phase=phase,
            dry_run=dry_run,
        )
    )


def _append_log(entry: dict) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as fout:
        fout.write(json.dumps(entry) + "\n")


def _append_prompt_markdown(payload: dict) -> None:
    if not PROMPT_LOG_PATH.exists():
        PROMPT_LOG_PATH.write_text("# Gemini Prompts Log\n\n", encoding="utf-8")
    repo = payload.get("repo_path") or "unspecified"
    branch = payload.get("branch") or "current"
    phase = payload.get("phase") or "unspecified"
    session = payload.get("session_name") or payload.get("session_id") or "unspecified"
    ts = payload.get("ts")
    instruction = payload.get("instruction", "").strip().replace("\n", " ")
    line = f"- {ts}: `{instruction}` _(repo: {repo}, branch: {branch}, phase: {phase}, session: {session})_\n"
    with PROMPT_LOG_PATH.open("a", encoding="utf-8") as fout:
        fout.write(line)


def _format_instruction(payload: dict) -> str:
    lines = [
        "# Gemini CLI Task",
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