"""Ops pack tools with simple persistence for tickets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Dict

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
