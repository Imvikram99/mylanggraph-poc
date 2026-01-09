"""Shared context store helpers."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_SCHEMA_VERSION = 1

PLANNING_CONTEXT_PATH = Path("data/context/planning_context.json")
IMPLEMENTATION_CONTEXT_PATH = Path("data/context/implementation_context.json")
PLANNING_SESSIONS_PATH = Path("data/context/planning_sessions.local.json")
IMPLEMENTATION_SESSIONS_PATH = Path("data/context/implementation_sessions.local.json")
SUMMARY_PATH = Path("docs/context_summary.md")

DEFAULT_PINNED_RULES = [
    "Repo state is truth; never assume unstated facts.",
    "Evidence required for done/implemented/fixed claims.",
    "If unsure, request file pointers instead of guessing.",
]

PLANNING_BUDGETS = {
    "pinned": 350,
    "diff": 600,
    "repo": 150,
    "decisions": 600,
    "summary": 800,
    "files": 300,
    "retrieved": 300,
}

IMPLEMENTATION_BUDGETS = {
    "pinned": 350,
    "diff": 600,
    "tasks": 400,
    "evidence": 150,
    "retrieved": 200,
}


def load_context_store(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"schema_version": DEFAULT_SCHEMA_VERSION, "entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": DEFAULT_SCHEMA_VERSION, "entries": []}
    if not isinstance(data, dict):
        return {"schema_version": DEFAULT_SCHEMA_VERSION, "entries": []}
    data.setdefault("schema_version", DEFAULT_SCHEMA_VERSION)
    data.setdefault("entries", [])
    return data


def save_context_store(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_sessions_store(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"schema_version": DEFAULT_SCHEMA_VERSION, "entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": DEFAULT_SCHEMA_VERSION, "entries": []}
    if not isinstance(data, dict):
        return {"schema_version": DEFAULT_SCHEMA_VERSION, "entries": []}
    data.setdefault("schema_version", DEFAULT_SCHEMA_VERSION)
    data.setdefault("entries", [])
    return data


def save_sessions_store(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_context_path(mode: str) -> Path:
    return PLANNING_CONTEXT_PATH if mode == "planning" else IMPLEMENTATION_CONTEXT_PATH


def resolve_sessions_path(mode: str) -> Path:
    return PLANNING_SESSIONS_PATH if mode == "planning" else IMPLEMENTATION_SESSIONS_PATH


def resolve_key(repo_path: str, branch: str | None, workstream_id: str) -> Dict[str, str]:
    return {
        "repo": str(Path(repo_path).resolve()),
        "branch": branch or "current",
        "workstream_id": workstream_id or "default",
    }


def find_entry(store: Dict[str, Any], key: Dict[str, str]) -> Optional[Dict[str, Any]]:
    for entry in store.get("entries", []):
        if entry.get("key") == key:
            return entry
    return None


def upsert_entry(store: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    entries = store.setdefault("entries", [])
    for idx, existing in enumerate(entries):
        if existing.get("key") == entry.get("key"):
            entries[idx] = entry
            return entry
    entries.append(entry)
    return entry


def ensure_entry(
    store: Dict[str, Any],
    *,
    key: Dict[str, str],
    feature_request: str | None = None,
) -> Dict[str, Any]:
    entry = find_entry(store, key)
    if entry:
        return entry
    entry = {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "key": key,
        "feature_request": feature_request or "",
        "checkpoint": {},
        "pinned_rules": list(DEFAULT_PINNED_RULES),
        "working_summary": {"text": "", "updated_at": "", "stale": False},
        "open_decisions": [],
        "evidence_ledger": [],
        "cli_sessions": {},
        "last_run": {},
        "file_pointers": [],
    }
    upsert_entry(store, entry)
    return entry


def compute_repo_state(repo_path: str, baseline_commit: str | None = None) -> Dict[str, Any]:
    repo = Path(repo_path)
    head = _run_git(repo, ["rev-parse", "HEAD"])
    tracked_hash = _tracked_files_hash(repo)
    diff_files = _diff_files(repo, baseline_commit)
    return {
        "git_head": head,
        "tracked_files_hash": tracked_hash,
        "diff_files": diff_files,
    }


def summary_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_context_bundle(
    *,
    mode: str,
    entry: Dict[str, Any],
    repo_state: Dict[str, Any],
    file_pointers: List[str] | None = None,
    retrieved_snippets: List[str] | None = None,
    task_checklist: List[str] | None = None,
) -> str:
    budgets = PLANNING_BUDGETS if mode == "planning" else IMPLEMENTATION_BUDGETS
    sections: List[str] = []

    pinned = entry.get("pinned_rules") or DEFAULT_PINNED_RULES
    sections.append(_format_section("Pinned rules", [f"- {rule}" for rule in pinned], budgets["pinned"]))

    stale = bool(entry.get("working_summary", {}).get("stale"))
    if mode == "planning":
        if stale:
            diff_lines = _diff_lines(repo_state, stale)
            if diff_lines:
                sections.append(_format_section("Diff-first summary", diff_lines, budgets["diff"]))
        repo_line = _repo_checkpoint_line(repo_state, stale)
        sections.append(_format_section("Repo checkpoint", [repo_line], budgets["repo"]))
        decisions = entry.get("open_decisions") or []
        decision_lines = _decision_lines(decisions)
        if decision_lines:
            sections.append(_format_section("Open decisions", decision_lines, budgets["decisions"]))
        summary_text = entry.get("working_summary", {}).get("text") or ""
        if summary_text:
            header = "Working summary (STALE - do not trust)" if stale else "Working summary"
            summary_lines = _wrap_text(summary_text)
            sections.append(_format_section(header, summary_lines, budgets["summary"]))
        if file_pointers:
            sections.append(_format_section("File pointers", [f"- {item}" for item in file_pointers], budgets["files"]))
        if retrieved_snippets:
            sections.append(_format_section("Retrieved snippets", _prefix_lines(retrieved_snippets), budgets["retrieved"]))
    else:
        diff_lines = _diff_lines(repo_state, stale)
        if diff_lines:
            sections.append(_format_section("Diff-first summary", diff_lines, budgets["diff"]))
        if task_checklist:
            sections.append(
                _format_section("Next steps", [f"- {item}" for item in task_checklist], budgets["tasks"])
            )
        sections.append(
            _format_section(
                "Evidence reminder",
                ["- Claims require file paths and line refs or symbol names."],
                budgets["evidence"],
            )
        )
        if retrieved_snippets:
            sections.append(_format_section("Retrieved snippets", _prefix_lines(retrieved_snippets), budgets["retrieved"]))

    cleaned = [section for section in sections if section]
    return "\n\n".join(cleaned).strip()


def render_context_summary_markdown(
    *,
    planning_entry: Dict[str, Any] | None,
    implementation_entry: Dict[str, Any] | None,
) -> str:
    lines = ["# Shared Context Summary", ""]
    lines.extend(_render_entry_summary("Planning", planning_entry))
    lines.append("")
    lines.extend(_render_entry_summary("Implementation", implementation_entry))
    return "\n".join(lines).strip() + "\n"


def _render_entry_summary(label: str, entry: Dict[str, Any] | None) -> List[str]:
    if not entry:
        return [f"## {label}", "", "_No data_"]
    summary = entry.get("working_summary", {}).get("text") or ""
    decisions = entry.get("open_decisions") or []
    last_run = entry.get("last_run") or {}
    lines = [f"## {label}", ""]
    if summary:
        lines.append("Summary:")
        lines.append(summary)
        lines.append("")
    if decisions:
        lines.append("Open decisions:")
        for decision in decisions[:5]:
            text = decision.get("text") if isinstance(decision, dict) else str(decision)
            lines.append(f"- {text}")
        lines.append("")
    if last_run:
        status = last_run.get("status", "unknown")
        error = last_run.get("error")
        next_action = last_run.get("next_action")
        lines.append(f"Last run: {status}")
        if error:
            lines.append(f"Error: {error}")
        if next_action:
            lines.append(f"Next action: {next_action}")
    return lines


def _run_git(repo: Path, args: List[str]) -> Optional[str]:
    import time
    start = time.time()
    cmd_str = f"git {' '.join(args)}"
    print(f"[DEBUG] running {cmd_str} in {repo}...")
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
        duration = time.time() - start
        print(f"[DEBUG] finished {cmd_str} in {duration:.2f}s (ret={proc.returncode})")
    except OSError as e:
        print(f"[DEBUG] failed {cmd_str}: {e}")
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip()


def _tracked_files_hash(repo: Path) -> str:
    files = _run_git(repo, ["ls-files", "-z"]) or ""
    status = _run_git(repo, ["status", "--porcelain"]) or ""
    data = f"{files}\n{status}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _diff_files(repo: Path, baseline_commit: str | None) -> List[str]:
    if not baseline_commit:
        status = _run_git(repo, ["status", "--porcelain"]) or ""
        return [line[3:] for line in status.splitlines() if line.strip()]
    diff = _run_git(repo, ["diff", "--name-only", f"{baseline_commit}..HEAD"]) or ""
    return [line.strip() for line in diff.splitlines() if line.strip()]


def _repo_checkpoint_line(repo_state: Dict[str, Any], stale: bool) -> str:
    head = repo_state.get("git_head") or "unknown"
    tracked = repo_state.get("tracked_files_hash") or "unknown"
    status = "STALE" if stale else "fresh"
    return f"head={head} tracked_hash={tracked} status={status}"


def _diff_lines(repo_state: Dict[str, Any], stale: bool) -> List[str]:
    diff_files = repo_state.get("diff_files") or []
    if not diff_files and not stale:
        return []
    lines = []
    if stale:
        lines.append("- Context is STALE; refresh file evidence before changes.")
    if diff_files:
        lines.append("Changed files:")
        lines.extend(f"- {path}" for path in diff_files[:20])
    return lines


def _decision_lines(decisions: Iterable[Any]) -> List[str]:
    lines: List[str] = []
    for decision in list(decisions)[-5:]:
        if isinstance(decision, dict):
            text = decision.get("text") or decision.get("id") or ""
            status = decision.get("status")
            if status:
                text = f"{text} ({status})"
        else:
            text = str(decision)
        if text:
            lines.append(f"- {text}")
    return lines


def _format_section(title: str, lines: List[str], limit: int) -> str:
    if not lines:
        return ""
    header = f"{title}:"
    output = [header]
    used = len(header) + 1
    for line in lines:
        candidate = line.rstrip()
        if not candidate:
            continue
        if used + len(candidate) + 1 > limit:
            break
        output.append(candidate)
        used += len(candidate) + 1
    return "\n".join(output)


def _wrap_text(text: str) -> List[str]:
    return [line for line in text.strip().splitlines() if line.strip()]


def _prefix_lines(lines: List[str]) -> List[str]:
    prefixed: List[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        prefixed.append(f"- {line}")
    return prefixed


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
