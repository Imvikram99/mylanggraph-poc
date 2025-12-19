"""Tenant registry for per-tenant rate limits + feature flags."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


class TenantRegistry:
    def __init__(self, path: Path | str = Path("configs/tenants.yaml")) -> None:
        self.path = Path(path)
        self._cache = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"tenants": {"default": {}}}
        with self.path.open("r", encoding="utf-8") as fin:
            return yaml.safe_load(fin) or {"tenants": {"default": {}}}

    def get(self, tenant_id: str) -> Dict[str, Any]:
        tenants = self._cache.get("tenants", {})
        return tenants.get(tenant_id) or tenants.get("default", {})
