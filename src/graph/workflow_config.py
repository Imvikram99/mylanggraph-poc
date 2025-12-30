"""Helpers for loading workflow template configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def load_workflow_config(path: str | Path = "configs/workflows.yaml") -> Dict[str, Any]:
    """Load architect/reviewer/tech-lead templates."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Workflow config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fin:
        return yaml.safe_load(fin) or {}
