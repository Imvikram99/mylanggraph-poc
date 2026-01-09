from pathlib import Path

from src.context.store import (
    build_context_bundle,
    ensure_entry,
    load_context_store,
    resolve_key,
    save_context_store,
    summary_hash,
)


def test_context_store_roundtrip(tmp_path: Path) -> None:
    store_path = tmp_path / "planning_context.json"
    store = load_context_store(store_path)
    key = resolve_key(repo_path=str(tmp_path), branch="main", workstream_id="ws-1")
    entry = ensure_entry(store, key=key, feature_request="Share context")
    entry["working_summary"]["text"] = "Summary here."
    save_context_store(store_path, store)

    loaded = load_context_store(store_path)
    loaded_entry = next(item for item in loaded["entries"] if item["key"] == key)
    assert loaded_entry["feature_request"] == "Share context"
    assert loaded_entry["working_summary"]["text"] == "Summary here."


def test_context_bundle_includes_stale_marker() -> None:
    entry = {
        "pinned_rules": ["Rule A"],
        "working_summary": {"text": "Old summary", "stale": True},
        "open_decisions": [{"text": "Decision 1", "status": "open"}],
    }
    repo_state = {"git_head": "abc", "tracked_files_hash": "hash", "diff_files": ["file.py"]}
    bundle = build_context_bundle(
        mode="planning",
        entry=entry,
        repo_state=repo_state,
        file_pointers=["docs/plan.md"],
    )
    assert "STALE" in bundle
    assert "Diff-first summary" in bundle


def test_summary_hash_stable() -> None:
    text = "Example summary."
    assert summary_hash(text) == summary_hash(text)


def test_evidence_gate_blocks_on_claims() -> None:
    import pytest

    from src.graph.nodes.context import EvidenceGateNode

    node = EvidenceGateNode(config={"shared_context": {"enabled": True}})
    state = {
        "context": {"share_session": True},
        "output": "Implemented the API changes.",
    }
    with pytest.raises(ValueError):
        node.run(state)
