"""Helpers to load model manifests and policy presets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

DEFAULT_MODELS_PATH = Path(os.getenv("MODELS_CONFIG_PATH", "configs/models.yaml"))


def load_models_manifest(path: str | Path = DEFAULT_MODELS_PATH) -> List[Dict[str, Any]]:
    data = _load_yaml(path)
    return data.get("models", [])


def load_policy_config(path: str | Path = DEFAULT_MODELS_PATH) -> Dict[str, Any]:
    data = _load_yaml(path)
    return data.get("policies", {})


def _load_yaml(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fin:
        return yaml.safe_load(fin) or {}
