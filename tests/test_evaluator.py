from pathlib import Path

from src.graph.nodes.evaluator import EvaluatorNode
from src.rlhf.reward import RewardScorer


def test_evaluator_logs_metrics(tmp_path):
    metrics_file = tmp_path / "metrics.jsonl"
    node = EvaluatorNode(metrics_path=str(metrics_file), threshold=0.2)
    state = {
        "artifacts": [{"text": "A"}, {"text": "B"}],
        "output": "This is a reasonably long output that should score well." * 2,
        "context": {"scenario_id": "demo"},
        "metadata": {},
        "route": "rag",
    }
    result = node.run(state)
    evaluations = result["metadata"]["evaluations"]
    assert evaluations
    assert metrics_file.exists()
    lines = metrics_file.read_text(encoding="utf-8").strip().splitlines()
    assert lines


class FixedReward(RewardScorer):
    def __init__(self):
        pass

    def score(self, output: str, model_path=None) -> float:  # type: ignore[override]
        return 0.75


def test_evaluator_uses_reward_score(tmp_path):
    node = EvaluatorNode(metrics_path=str(tmp_path / "metrics.jsonl"), threshold=0.2, reward_scorer=FixedReward())
    state = {
        "artifacts": [{"text": "A"}],
        "output": "Aligned ship success",
        "context": {"scenario_id": "demo"},
        "metadata": {},
        "plan": {"phases": [{"name": "Phase 1"}]},
        "route": "workflow",
    }
    result = node.run(state)
    assert result["metadata"]["reward_score"] == 0.75
