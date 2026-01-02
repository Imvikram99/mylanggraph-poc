"""Command run telemetry and retrieval helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

LOG_PATH = Path("data/ops/command_runs.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_SECTION_RE = re.compile(r"^##\s+(.+)$", re.M)
_WORKDIR_RE = re.compile(r"workdir:\s*`([^`]+)`", re.IGNORECASE)
_CODE_BLOCK_RE = re.compile(r"```(.*?)```", re.S)


def log_report_commands(
    *,
    repo_workspace: Path,
    report_paths: Iterable[str],
    repo_path: str,
    branch: Optional[str],
    phase: Optional[str],
    session_id: Optional[str],
    session_name: Optional[str],
) -> int:
    total = 0
    for report_path in report_paths:
        full_path = repo_workspace / report_path
        if not full_path.exists():
            continue
        text = full_path.read_text(encoding="utf-8", errors="ignore")
        entries = extract_report_commands(
            text,
            report_path=report_path,
            repo_path=repo_path,
            branch=branch,
            phase=phase,
            session_id=session_id,
            session_name=session_name,
        )
        if entries:
            _append_entries(entries)
            total += len(entries)
    return total


def extract_report_commands(
    text: str,
    *,
    report_path: str,
    repo_path: str,
    branch: Optional[str],
    phase: Optional[str],
    session_id: Optional[str],
    session_name: Optional[str],
) -> List[Dict[str, Any]]:
    sections = _split_sections(text)
    entries: List[Dict[str, Any]] = []
    for section, body in sections:
        command_text = _extract_labeled_code_block(body, "Command")
        result_text = _extract_labeled_code_block(body, "Result")
        workdir = _extract_workdir(body)
        if not command_text and not result_text:
            continue
        status = _infer_status(command_text, result_text)
        error_signature = _extract_error_signature(result_text) if status == "failed" else None
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "repo_path": repo_path,
            "branch": branch,
            "phase": phase,
            "session_id": session_id,
            "session_name": session_name,
            "report_path": report_path,
            "section": section,
            "command": command_text,
            "workdir": workdir,
            "status": status,
            "result_excerpt": (result_text or "").strip()[:800],
            "error_signature": error_signature,
            "error_hash": _hash_signature(error_signature),
        }
        entries.append(entry)
    return entries


def load_command_hints(
    *,
    repo_path: str,
    phase: Optional[str] = None,
    limit: int = 4,
) -> List[str]:
    if not LOG_PATH.exists():
        return []
    hints: List[str] = []
    pending_failures: Dict[tuple[str, str], Dict[str, Any]] = {}
    seen: set[str] = set()
    for entry in _load_entries():
        if entry.get("repo_path") != repo_path:
            continue
        if phase and entry.get("phase") != phase:
            continue
        section = str(entry.get("section") or "unknown")
        workdir = str(entry.get("workdir") or "")
        key = (section, workdir)
        status = entry.get("status")
        if status == "failed":
            pending_failures[key] = entry
            continue
        if status != "success":
            continue
        failure = pending_failures.get(key)
        if not failure:
            continue
        hint = _format_hint(failure, entry)
        if hint and hint not in seen:
            hints.append(hint)
            seen.add(hint)
        if len(hints) >= limit:
            break
    return hints


def _split_sections(text: str) -> List[tuple[str, str]]:
    sections: List[tuple[str, str]] = []
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return sections
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        name = match.group(1).strip()
        body = text[start:end].strip()
        sections.append((name, body))
    return sections


def _extract_labeled_code_block(text: str, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}.*?```(.*?)```", re.S | re.IGNORECASE)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    # fallback: next non-empty line after label
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith(label.lower()):
            for next_line in lines[idx + 1 :]:
                if next_line.strip():
                    return next_line.strip()
    return ""


def _extract_workdir(text: str) -> str:
    match = _WORKDIR_RE.search(text)
    return match.group(1).strip() if match else ""


def _infer_status(command_text: str, result_text: str) -> str:
    command_lower = (command_text or "").strip().lower()
    result_lower = (result_text or "").strip().lower()
    if not command_text or command_lower.startswith("n/a"):
        return "skipped"
    if _is_skipped_result(result_lower):
        return "skipped"
    if _is_failure_result(result_lower):
        return "failed"
    if result_text:
        return "success"
    return "unknown"


def _is_skipped_result(text: str) -> bool:
    return any(token in text for token in ("not run", "skipped", "deferred"))


def _is_failure_result(text: str) -> bool:
    if "build failure" in text or "build failed" in text:
        return True
    if "operation not permitted" in text or "permission denied" in text:
        return True
    if _nonzero_test_counts(text):
        return True
    if _has_error_line(text):
        return True
    return False


def _nonzero_test_counts(text: str) -> bool:
    failures = _count_metric(text, "failures")
    errors = _count_metric(text, "errors")
    return (failures is not None and failures > 0) or (errors is not None and errors > 0)


def _count_metric(text: str, label: str) -> Optional[int]:
    match = re.search(rf"{label}\s*:\s*(\d+)", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _has_error_line(text: str) -> bool:
    for line in text.splitlines():
        lowered = line.strip().lower()
        if not lowered:
            continue
        if "error" in lowered or "exception" in lowered or "failed to" in lowered:
            if "errors: 0" in lowered or "failures: 0" in lowered:
                continue
            return True
    return False


def _extract_error_signature(result_text: str) -> Optional[str]:
    for line in result_text.splitlines():
        lowered = line.strip().lower()
        if not lowered:
            continue
        if "build failure" in lowered or "operation not permitted" in lowered:
            return line.strip()[:240]
        if "permission denied" in lowered or "failed to execute goal" in lowered:
            return line.strip()[:240]
        if "exception" in lowered or ("error" in lowered and "errors: 0" not in lowered):
            return line.strip()[:240]
    return None


def _hash_signature(signature: Optional[str]) -> Optional[str]:
    if not signature:
        return None
    return sha1(signature.encode("utf-8")).hexdigest()[:12]


def _format_hint(failure: Dict[str, Any], success: Dict[str, Any]) -> str:
    section = failure.get("section") or "command"
    signature = failure.get("error_signature") or "failure"
    command = success.get("command") or ""
    workdir = success.get("workdir") or "."
    if not command:
        return ""
    return f"{section} failed before ({signature}); last working command: `{command}` (workdir: {workdir})."


def _append_entries(entries: Iterable[Dict[str, Any]]) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as fout:
        for entry in entries:
            fout.write(json.dumps(entry) + "\n")


def _load_entries() -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    with LOG_PATH.open("r", encoding="utf-8") as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries
