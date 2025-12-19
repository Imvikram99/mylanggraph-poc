"""Pipeline orchestration for RLHF / DPO."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .preferences import PreferenceStore
from .reward import train_reward_model
from ..services.experiment_tracker import ExperimentTracker


def run_pipeline(
    *,
    output_dir: Path = Path("data/rlhf"),
    preferences_path: Path = Path("data/annotations/preferences.jsonl"),
) -> Dict[str, str]:
    store = PreferenceStore(preferences_path)
    prefs = store.list()
    reward_weights = train_reward_model(prefs, output_dir / "reward_model.json")
    policy_path = output_dir / "policy_stub.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text('{"status": "policy_updated"}', encoding="utf-8")
    bias = store.bias_metrics()
    result = {
        "reward_model": str(output_dir / "reward_model.json"),
        "policy": str(policy_path),
        "bias": bias,
        "reward_weights": reward_weights,
    }
    ExperimentTracker().log(
        run_type="rlhf_pipeline",
        params={"preferences_path": str(preferences_path), "output_dir": str(output_dir)},
        metrics={"bias": bias, "reward_weights": reward_weights},
    )
    return result
