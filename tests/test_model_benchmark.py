from pathlib import Path

from src.models.benchmarking import benchmark_models, write_results


def test_benchmark_models_generates_scores(tmp_path):
    models = [
        {"name": "model-a", "provider": "test", "cost_per_1k": 0.002, "latency_ms": 1000},
        {"name": "model-b", "provider": "test", "cost_per_1k": 0.001, "latency_ms": 800},
    ]
    tasks = [{"name": "task", "weight": 1.0}]
    results = benchmark_models(models, tasks)
    assert len(results) == 2
    assert all("score" in row for row in results)
    output = tmp_path / "bench.jsonl"
    write_results(results, output)
    assert output.exists()
    assert len(output.read_text().strip().splitlines()) == 2
