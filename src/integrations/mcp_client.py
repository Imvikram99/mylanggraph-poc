"""MCP tool registry utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml
from rich.console import Console

console = Console()


class MCPToolRegistry:
    """Load MCP tool definitions from YAML."""

    def __init__(self, config_path: str = "configs/mcp_tools.yaml") -> None:
        self.path = Path(config_path)
        self.registry = self._load()

    def _load(self) -> Dict[str, Dict]:
        if not self.path.exists():
            console.log(f"[yellow]MCP registry not found at {self.path}[/]")
            return {}
        with self.path.open("r", encoding="utf-8") as fin:
            data = yaml.safe_load(fin) or {}
        return data.get("servers", {})

    def enabled_servers(self) -> List[str]:
        return [name for name, cfg in self.registry.items() if cfg.get("enabled", False)]

    def describe(self) -> str:
        enabled = self.enabled_servers()
        if not enabled:
            return "No MCP servers enabled."
        descriptions = [f"{name} ({self.registry[name].get('type', 'custom')})" for name in enabled]
        return "Enabled MCP servers: " + ", ".join(descriptions)
