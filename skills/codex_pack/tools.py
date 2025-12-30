"""Codex CLI helper tools."""

from __future__ import annotations

from typing import Optional

from scripts.ops.codex_proxy import dispatch


def request_codex(
    instruction: str,
    repo_path: Optional[str] = None,
    branch: Optional[str] = None,
    dry_run: bool = False,
) -> str:
    """Forward an instruction to the Codex CLI via the proxy script."""
    return dispatch(instruction, repo_path=repo_path, branch=branch, dry_run=dry_run)
