"""Model policy helpers to influence routing/strategy."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


class ModelPolicy:
    """Evaluate policy presets (cost-sensitive, latency-sensitive, etc.)."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.default = self.config.get("default", "balanced")
        self.presets: Dict[str, Dict[str, Any]] = self.config.get("presets", {})

    def advise(self, context: Dict[str, Any]) -> Dict[str, Any]:
        name = (
            context.get("model_policy")
            or os.getenv("MODEL_POLICY")
            or self.config.get("default")
            or self.default
        )
        preset = self.presets.get(name, {})
        preset.setdefault("name", name)
        preset.setdefault("boost", 0.15)
        return preset
