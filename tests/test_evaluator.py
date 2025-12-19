from pathlib import Path

from src.graph.nodes.evaluator import EvaluatorNode


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
