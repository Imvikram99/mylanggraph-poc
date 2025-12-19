from pathlib import Path

from src.rlhf.preferences import Preference, PreferenceStore
from src.rlhf.reward import train_reward_model
from src.rlhf.pipeline import run_pipeline


def test_preference_store(tmp_path):
    path = tmp_path / "prefs.jsonl"
    store = PreferenceStore(path)
    store.add(Preference(prompt="p", response_a="a", response_b="b", winner="A", annotator_id="ann"))
    prefs = store.list()
    assert len(prefs) == 1
    metrics = store.bias_metrics()
    assert metrics["annotators"] == 1


def test_reward_training(tmp_path):
    prefs = [
        {"prompt": "p", "response_a": "a", "response_b": "b", "winner": "A"},
        {"prompt": "p", "response_a": "a", "response_b": "b", "winner": "B"},
    ]
    output = tmp_path / "reward.json"
    weights = train_reward_model(prefs, output)
    assert output.exists()
    assert "w_pref" in weights


def test_pipeline(tmp_path):
    prefs = tmp_path / "prefs.jsonl"
    prefs.write_text('{"prompt": "p", "response_a": "a", "response_b": "b", "winner": "A", "annotator_id": "ann"}\n')
    result = run_pipeline(output_dir=tmp_path / "rlhf", preferences_path=prefs)
    assert Path(result["reward_model"]).exists()
