"""Feature flag helper for FastAPI + runner integrations."""

from __future__ import annotations

import os
from typing import Dict


class FeatureFlags:
    def __init__(self, defaults: Dict[str, bool] | None = None) -> None:
        self.defaults = defaults or {"agent_run": True, "streaming": True}

    def is_enabled(self, name: str, tenant_flags: Dict[str, bool] | None = None) -> bool:
        env_key = f"FEATURE_{name.upper()}"
        if env_key in os.environ:
            return os.getenv(env_key, "false").lower() == "true"
        flags = tenant_flags or {}
        if name in flags:
            return bool(flags[name])
        return self.defaults.get(name, False)

    def snapshot(self, tenant_flags: Dict[str, bool] | None = None) -> Dict[str, bool]:
        return {name: self.is_enabled(name, tenant_flags) for name in self.defaults.keys()}
