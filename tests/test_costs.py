import json

from src.observability.costs import CostLatencyTracker


def test_cost_tracker_logs_workflow_phase(tmp_path):
    tracker = CostLatencyTracker(path=tmp_path / "cost.jsonl")

    def handler(state):
        state["workflow_phase"] = "implementation"
        return state

    wrapped = tracker.wrap("node", handler)
    wrapped({"workflow_phase": "architecture"})
    tracker.flush("scenario", "workflow")
    data = json.loads((tmp_path / "cost.jsonl").read_text(encoding="utf-8"))
    assert data["workflow_phase"] == "implementation"
