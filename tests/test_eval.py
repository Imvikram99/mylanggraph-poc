from pathlib import Path

from src.eval.suite import EvaluationSuite
from src.eval.governance import GovernanceLogger


def test_evaluation_suite(tmp_path):
    suite = EvaluationSuite(output_path=tmp_path / "eval.jsonl")
    state = {"output": "Safe summary", "artifacts": [{}], "context": {"scenario_id": "t"}, "route": "rag"}
    metrics = suite.evaluate(state)
    assert metrics["relevance"] > 0
    assert (tmp_path / "eval.jsonl").exists()


def test_governance_logger(tmp_path):
    logger = GovernanceLogger(path=tmp_path / "gov.jsonl")
    state = {
        "output": "No pii here",
        "context": {"scenario_id": "demo"},
        "route": "workflow",
        "plan": {"phases": [{"name": "Phase 1", "owner": "architect"}]},
        "metadata": {
            "telemetry": {"cost_estimate_usd": 0.01, "latency_s": 1.2},
            "code_review": {"status": "approved"},
        },
    }
    result = logger.log(state)
    assert result["pii_detected"] is False
    contents = (tmp_path / "gov.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert any("Phase 1" in line for line in contents)
