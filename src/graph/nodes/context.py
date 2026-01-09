"""Shared context nodes for cross-session continuity."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console

from ...context.store import (
    DEFAULT_PINNED_RULES,
    build_context_bundle,
    compute_repo_state,
    ensure_entry,
    load_context_store,
    load_sessions_store,
    now_iso,
    render_context_summary_markdown,
    resolve_context_path,
    resolve_key,
    resolve_sessions_path,
    save_context_store,
    save_sessions_store,
    summary_hash,
    upsert_entry,
)
from ...memory.temporal import TemporalMemoryStore

console = Console()


class ContextLoadNode:
    """Load shared context from the repo and attach it to state."""

    def __init__(
        self,
        config: Dict[str, Any],
        *,
        mode: str,
        memory_store: TemporalMemoryStore | None = None,
    ) -> None:
        self.config = config
        self.mode = mode
        self.memory_store = memory_store

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if not _shared_context_enabled(state, self.config):
            return state
        plan = state.setdefault("plan", {})
        metadata = plan.setdefault("metadata", {})
        context = state.setdefault("context", {})

        repo_path = _resolve_repo_path(context, metadata)
        branch = context.get("target_branch") or metadata.get("target_branch")
        feature_request = _resolve_feature_request(state, context, plan)
        workstream_id = _resolve_workstream_id(context, metadata, feature_request)

        store_path = resolve_context_path(self.mode)
        store = load_context_store(store_path)
        key = resolve_key(repo_path, branch, workstream_id)
        entry = ensure_entry(store, key=key, feature_request=feature_request)
        entry.setdefault("pinned_rules", list(DEFAULT_PINNED_RULES))

        sessions = _load_sessions_entry(self.mode, key)
        if sessions:
            _merge_sessions_into_metadata(metadata, sessions, self.mode)

        repo_state = compute_repo_state(repo_path, entry.get("checkpoint", {}).get("git_head"))
        stale = _is_stale(entry, repo_state)
        entry.setdefault("working_summary", {}).update({"stale": stale})

        file_pointers = _file_pointers_from_metadata(metadata)
        if entry.get("file_pointers"):
            file_pointers = _merge_file_pointers(file_pointers, entry.get("file_pointers"))

        retrieved_snippets = _retrieve_snippets(
            self.memory_store,
            feature_request,
            context,
        )

        task_checklist = _task_checklist(context)
        bundle = build_context_bundle(
            mode=self.mode,
            entry=entry,
            repo_state=repo_state,
            file_pointers=file_pointers,
            retrieved_snippets=retrieved_snippets,
            task_checklist=task_checklist,
        )

        shared = metadata.setdefault("shared_context", {})
        shared[self.mode] = {
            "entry": entry,
            "repo_state": repo_state,
            "bundle": bundle,
        }
        metadata.setdefault("context_bundle", {})[self.mode] = bundle
        metadata["workstream_id"] = workstream_id
        metadata["shared_context_enabled"] = True

        context["workstream_id"] = workstream_id
        context["context_bundle"] = metadata.get("context_bundle", {})
        context["shared_context_enabled"] = True
        if stale:
            context["shared_context_stale"] = True
        console.log(f"[cyan]ContextLoad[/] mode={self.mode} workstream={workstream_id} stale={stale}")
        return state


class ContextWriteNode:
    """Persist updated context back to the repo store."""

    def __init__(self, config: Dict[str, Any], *, mode: str) -> None:
        self.config = config
        self.mode = mode

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if not _shared_context_enabled(state, self.config):
            return state
        plan = state.get("plan") or {}
        metadata = plan.get("metadata") or {}
        context = state.get("context") or {}

        repo_path = _resolve_repo_path(context, metadata)
        branch = context.get("target_branch") or metadata.get("target_branch")
        feature_request = _resolve_feature_request(state, context, plan)
        workstream_id = _resolve_workstream_id(context, metadata, feature_request)

        store_path = resolve_context_path(self.mode)
        store = load_context_store(store_path)
        key = resolve_key(repo_path, branch, workstream_id)
        entry = ensure_entry(store, key=key, feature_request=feature_request)

        entry["feature_request"] = feature_request or entry.get("feature_request") or ""
        entry["pinned_rules"] = entry.get("pinned_rules") or list(DEFAULT_PINNED_RULES)
        entry["file_pointers"] = _file_pointers_from_metadata(metadata)
        entry["open_decisions"] = context.get("open_decisions") or entry.get("open_decisions") or []
        entry["evidence_ledger"] = context.get("evidence_ledger") or entry.get("evidence_ledger") or []

        repo_state = compute_repo_state(repo_path, None)
        checkpoint = entry.setdefault("checkpoint", {})
        checkpoint["git_head"] = repo_state.get("git_head") or checkpoint.get("git_head")
        checkpoint["tracked_files_hash"] = repo_state.get("tracked_files_hash") or checkpoint.get("tracked_files_hash")

        if self.mode == "planning":
            summary_text = plan.get("summary") or ""
            if summary_text and _allow_summary_update(state, "plan_summary"):
                entry["working_summary"] = {
                    "text": summary_text.strip(),
                    "updated_at": now_iso(),
                    "stale": False,
                }
                checkpoint["summary_hash"] = summary_hash(summary_text)
        entry["last_run"] = _last_run_record(state, entry.get("last_run", {}))

        upsert_entry(store, entry)
        save_context_store(store_path, store)

        sessions_path = resolve_sessions_path(self.mode)
        sessions_store = load_sessions_store(sessions_path)
        sessions_entry = _extract_sessions(state, key, self.mode)
        if sessions_entry:
            _upsert_sessions_entry(sessions_store, sessions_entry)
            save_sessions_store(sessions_path, sessions_store)

        _update_context_summary_markdown(workstream_id)
        console.log(f"[cyan]ContextWrite[/] mode={self.mode} workstream={workstream_id}")
        return state


class ValidationNode:
    """Validate shared context state before execution."""

    def __init__(self, config: Dict[str, Any], *, mode: str) -> None:
        self.config = config
        self.mode = mode

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if not _shared_context_enabled(state, self.config):
            return state
        plan = state.get("plan") or {}
        metadata = plan.get("metadata") or {}
        context = state.setdefault("context", {})
        shared = metadata.get("shared_context", {})
        entry = (shared.get(self.mode) or {}).get("entry") or {}

        stale = bool(entry.get("working_summary", {}).get("stale"))
        if stale:
            context["shared_context_stale"] = True

        violations = _evidence_violations(entry.get("evidence_ledger") or [])
        if violations:
            context["validation_block"] = True
            context["validation_reason"] = "; ".join(violations)
            console.log(f"[red]Context validation failed[/] {context['validation_reason']}")
        return state


class EvidenceGateNode:
    """Block outputs that claim completion without evidence."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if not _shared_context_enabled(state, self.config):
            return state
        output = str(state.get("output") or "")
        if not output:
            return state
        if not _has_completion_claim(output):
            return state
        context = state.setdefault("context", {})
        evidence = context.get("evidence_ledger") or []
        if evidence:
            return state
        reason = "Evidence required: add file paths + line refs for completion claims."
        context["validation_block"] = True
        context["validation_reason"] = reason
        console.log("[red]EvidenceGate[/] missing evidence ledger")
        raise ValueError(reason)


def _shared_context_enabled(state: Dict[str, Any], config: Dict[str, Any]) -> bool:
    context = state.get("context") or {}
    if "share_session" in context:
        return _coerce_bool(context.get("share_session"))
    if "shared_context" in context:
        return _coerce_bool(context.get("shared_context"))
    env_value = os.getenv("SHARED_CONTEXT_ENABLED")
    if env_value is not None:
        return _coerce_bool(env_value)
    cfg_value = (config.get("shared_context") or {}).get("enabled")
    return _coerce_bool(cfg_value)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _resolve_repo_path(context: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    repo_path = context.get("repo_path") or metadata.get("repo_path")
    if repo_path:
        return str(Path(repo_path).resolve())
    return str(Path.cwd().resolve())


def _resolve_feature_request(
    state: Dict[str, Any],
    context: Dict[str, Any],
    plan: Dict[str, Any],
) -> str:
    return (
        context.get("feature_request")
        or plan.get("request")
        or _last_user_message(state.get("messages") or [])
        or ""
    )


def _resolve_workstream_id(
    context: Dict[str, Any],
    metadata: Dict[str, Any],
    feature_request: str,
) -> str:
    value = context.get("workstream_id") or metadata.get("workstream_id")
    if value:
        return str(value)
    return _slugify(feature_request) or "default"


def _slugify(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text or "")
    collapsed = "-".join(part for part in cleaned.split("-") if part)
    return collapsed[:48]


def _last_user_message(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", "")).strip()
    return ""


def _file_pointers_from_metadata(metadata: Dict[str, Any]) -> List[str]:
    keys = [
        "product_file",
        "ui_ux_file",
        "architecture_file",
        "api_spec_file",
        "implementation_file",
        "lead_file",
        "tech_lead_file",
    ]
    pointers = []
    for key in keys:
        value = metadata.get(key)
        if value:
            pointers.append(str(value))
    return pointers


def _merge_file_pointers(primary: List[str], secondary: List[str]) -> List[str]:
    seen = set()
    merged: List[str] = []
    for item in primary + secondary:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _retrieve_snippets(
    memory_store: TemporalMemoryStore | None,
    feature_request: str,
    context: Dict[str, Any],
) -> List[str]:
    if not memory_store:
        return []
    if not _coerce_bool(context.get("shared_context_retrieve", False)):
        return []
    if not feature_request:
        return []
    results = memory_store.search(feature_request, top_k=3)
    snippets = []
    for item in results:
        text = item.get("text")
        score = float(item.get("score", 0))
        if text and score >= 0.5:
            snippets.append(str(text).strip())
    return snippets


def _task_checklist(context: Dict[str, Any]) -> List[str]:
    checklist = context.get("task_checklist")
    if isinstance(checklist, list):
        return [str(item) for item in checklist if str(item).strip()]
    return []


def _is_stale(entry: Dict[str, Any], repo_state: Dict[str, Any]) -> bool:
    checkpoint = entry.get("checkpoint") or {}
    head = checkpoint.get("git_head")
    tracked = checkpoint.get("tracked_files_hash")
    current_head = repo_state.get("git_head")
    current_tracked = repo_state.get("tracked_files_hash")
    if head and current_head and head != current_head:
        return True
    if tracked and current_tracked and tracked != current_tracked:
        return True
    return False


def _allow_summary_update(state: Dict[str, Any], checkpoint_name: str) -> bool:
    checkpoints = state.get("checkpoints") or []
    for checkpoint in checkpoints:
        if checkpoint.get("phase") == checkpoint_name:
            return True
    return False


def _last_run_record(state: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
    metadata = state.get("metadata") or {}
    code_review = metadata.get("code_review") or {}
    phase_exec = metadata.get("phase_execution") or {}
    blocked = phase_exec.get("blocked")
    status = "ok"
    error = None
    if code_review.get("status") and code_review.get("status") != "approved":
        status = "failed"
        error = "code_review_failed"
    if blocked:
        status = "failed"
        error = "phase_blocked"
    record = {
        "status": status,
        "error": error or previous.get("error"),
        "next_action": (state.get("context") or {}).get("next_action") or previous.get("next_action"),
        "updated_at": now_iso(),
    }
    return record


def _extract_sessions(state: Dict[str, Any], key: Dict[str, str], mode: str) -> Dict[str, Any] | None:
    plan = state.get("plan") or {}
    metadata = plan.get("metadata") or {}
    if mode == "planning":
        codex_sessions = metadata.get("codex_sessions")
        gemini_sessions = metadata.get("gemini_sessions")
    else:
        phase_exec = metadata.get("phase_execution") or {}
        codex_sessions = phase_exec.get("sessions")
        gemini_sessions = phase_exec.get("gemini_sessions")
    if not codex_sessions and not gemini_sessions:
        return None
    return {
        "key": key,
        "codex": codex_sessions or {},
        "gemini": gemini_sessions or {},
        "updated_at": now_iso(),
    }


def _upsert_sessions_entry(store: Dict[str, Any], entry: Dict[str, Any]) -> None:
    entries = store.setdefault("entries", [])
    for idx, existing in enumerate(entries):
        if existing.get("key") == entry.get("key"):
            entries[idx] = entry
            return
    entries.append(entry)


def _update_context_summary_markdown(workstream_id: str) -> None:
    planning_store = load_context_store(resolve_context_path("planning"))
    implementation_store = load_context_store(resolve_context_path("implementation"))
    planning_entry = _find_by_workstream(planning_store, workstream_id)
    implementation_entry = _find_by_workstream(implementation_store, workstream_id)
    summary = render_context_summary_markdown(
        planning_entry=planning_entry,
        implementation_entry=implementation_entry,
    )
    summary_path = Path("docs/context_summary.md")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")


def _find_by_workstream(store: Dict[str, Any], workstream_id: str) -> Dict[str, Any] | None:
    for entry in store.get("entries", []):
        key = entry.get("key") or {}
        if key.get("workstream_id") == workstream_id:
            return entry
    return None


def _load_sessions_entry(mode: str, key: Dict[str, str]) -> Dict[str, Any] | None:
    sessions_store = load_sessions_store(resolve_sessions_path(mode))
    for entry in sessions_store.get("entries", []):
        if entry.get("key") == key:
            return entry
    return None


def _merge_sessions_into_metadata(metadata: Dict[str, Any], sessions: Dict[str, Any], mode: str) -> None:
    if mode == "planning":
        if sessions.get("codex"):
            metadata.setdefault("codex_sessions", {}).update(sessions.get("codex", {}))
        if sessions.get("gemini"):
            metadata.setdefault("gemini_sessions", {}).update(sessions.get("gemini", {}))
        return
    phase_exec = metadata.setdefault("phase_execution", {})
    if sessions.get("codex"):
        phase_exec.setdefault("sessions", {}).update(sessions.get("codex", {}))
    if sessions.get("gemini"):
        phase_exec.setdefault("gemini_sessions", {}).update(sessions.get("gemini", {}))


def _evidence_violations(entries: List[Dict[str, Any]]) -> List[str]:
    violations: List[str] = []
    for entry in entries:
        files = entry.get("files") if isinstance(entry, dict) else None
        if not files:
            violations.append("Evidence ledger entry missing files")
            continue
        for file_entry in files:
            path = file_entry.get("path") if isinstance(file_entry, dict) else None
            if not path:
                violations.append("Evidence ledger entry missing file path")
    return violations


def _has_completion_claim(text: str) -> bool:
    lowered = text.lower()
    keywords = ("implemented", "fixed", "completed", "resolved", "done")
    return any(keyword in lowered for keyword in keywords)
