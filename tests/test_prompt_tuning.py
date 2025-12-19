from pathlib import Path

from src.models.prompt_tuning import score_prompt


def test_score_prompt():
    assert score_prompt("Please cite sources and analyze") > 0.5
