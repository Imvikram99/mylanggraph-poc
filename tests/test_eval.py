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
    result = logger.log({"output": "No pii here", "context": {}, "route": "rag"})
    assert result["pii_detected"] is False
