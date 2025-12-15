"""Skill hub node that loads and executes registered tools."""

from __future__ import annotations

import importlib
import yaml
from pathlib import Path
from typing import Any, Callable, Dict, List

from rich.console import Console

console = Console()


class SkillHubNode:
    """Dynamically route to registered skill packs."""

    def __init__(self, registry_path: str = "skills/registry.yaml") -> None:
        self.registry_path = Path(registry_path)
        self.packs = self._load_registry()

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        if not self.registry_path.exists():
            console.log("[yellow]No skill registry found, skipping skill packs[/]")
            return {}
        with self.registry_path.open("r", encoding="utf-8") as fin:
            raw = yaml.safe_load(fin) or {}
        return raw.get("packs", {})

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a skill based on `state['context']['skill']` or default pack."""
        context = state.get("context", {})
        requested_pack = context.get("skill_pack", "research_pack")
        requested_tool = context.get("skill_tool", "web_search")
        pack = self.packs.get(requested_pack)
        if not pack:
            console.log(f"[red]Unknown skill pack '{requested_pack}'[/]")
            return state

        try:
            result = self._call_tool(pack, requested_tool, state)
        except AttributeError:
            console.log(f"[red]Tool '{requested_tool}' missing in pack '{requested_pack}'[/]")
            return state
        message = {
            "role": "tool",
            "name": requested_tool,
            "content": result,
        }
        state.setdefault("messages", []).append(message)
        state["output"] = result
        return state

    def _call_tool(self, pack: Dict[str, Any], tool_name: str, state: Dict[str, Any]) -> Any:
        module_name = pack["module"]
        module = importlib.import_module(module_name)
        fn: Callable[..., Any] = getattr(module, tool_name)
        last_message = (state.get("messages") or [{}])[-1]
        content = last_message.get("content", "")
        return fn(content)
