from pathlib import Path

from src.data_pipeline.builder import build_corpus
from src.data_pipeline.quality import compute_quality_metrics


def test_build_corpus_and_manifest(tmp_path):
    input_dir = tmp_path / "docs"
    input_dir.mkdir()
    (input_dir / "a.txt").write_text("Hello world" * 20, encoding="utf-8")
    (input_dir / "b.md").write_text("Another document" * 10, encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    result = build_corpus(input_dir, "ds1", output_root=tmp_path, manifest_path=manifest, chunk_size=10)
    assert manifest.exists()
    assert "stats" in result
    dataset_file = Path(result["output"])
    metrics = compute_quality_metrics(dataset_file)
    assert metrics["chunks"] > 0
