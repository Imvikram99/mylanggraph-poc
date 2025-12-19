"""Skill hub node that loads and executes registered tools (including MCP)."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict

import yaml
from rich.console import Console

from ...integrations import MCPToolRegistry
from ..messages import append_message

console = Console()


@dataclass
class ToolDefinition:
    """Description for a registered tool function."""

    pack: str
    name: str
    description: str
    runner: Callable[..., Any]


class ToolNode:
    """Minimal ToolNode abstraction that normalizes execution and payloads."""

    def execute(self, definition: ToolDefinition, payload: Any) -> Any:
        try:
            if isinstance(payload, dict):
                return definition.runner(**payload)
            if payload is not None:
                return definition.runner(payload)
            return definition.runner()
        except TypeError:
            return definition.runner(payload)


class SkillHubNode(ToolNode):
    """Dynamically route to registered skill packs."""

    def __init__(self, registry_path: str = "skills/registry.yaml") -> None:
        super().__init__()
        self.registry_path = Path(registry_path)
        self.packs = self._load_registry()
        self.mcp_registry = MCPToolRegistry()
        self.dynamic_tools = self._build_mcp_tools()
        if self.dynamic_tools:
            self.packs["mcp"] = {
                "description": "Auto-registered MCP tools",
                "module": None,
                "tools": list(self.dynamic_tools.keys()),
            }
        self.tool_registry = self._discover_tools()

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        if not self.registry_path.exists():
            console.log("[yellow]No skill registry found, skipping skill packs[/]")
            return {}
        with self.registry_path.open("r", encoding="utf-8") as fin:
            raw = yaml.safe_load(fin) or {}
        return raw.get("packs", {})

    def _build_mcp_tools(self) -> Dict[str, Callable[..., Any]]:
        tools: Dict[str, Callable[..., Any]] = {}
        for name, cfg in self.mcp_registry.registry.items():
            if not cfg.get("enabled"):
                continue
            params = cfg.get("params", {})
            if cfg.get("type") == "builtin" and name == "filesystem":
                root = Path(params.get("root", ".")).resolve()
                tools["filesystem_read"] = self._filesystem_reader(root)
            else:
                tools[f"{name}_proxy"] = self._mcp_proxy(name, cfg.get("type", "custom"))
        if tools:
            console.log(f"[green]Loaded {len(tools)} MCP-backed tool(s).[/]")
        return tools

    def _discover_tools(self) -> Dict[str, ToolDefinition]:
        tools: Dict[str, ToolDefinition] = {}
        for pack_name, cfg in self.packs.items():
            module_name = cfg.get("module")
            registered = cfg.get("tools", [])
            if module_name:
                module = importlib.import_module(module_name)
                for tool_name in registered:
                    fn = getattr(module, tool_name)
                    key = self._tool_key(pack_name, tool_name)
                    tools[key] = ToolDefinition(
                        pack=pack_name,
                        name=tool_name,
                        description=getattr(fn, "__doc__", "") or cfg.get("description", ""),
                        runner=fn,
                    )
            else:
                for tool_name in registered:
                    fn = self.dynamic_tools.get(tool_name)
                    if fn is None:
                        continue
                    key = self._tool_key(pack_name, tool_name)
                    tools[key] = ToolDefinition(
                        pack=pack_name,
                        name=tool_name,
                        description=cfg.get("description", ""),
                        runner=fn,
                    )
        return tools

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a skill based on `state['context']['skill']` or default pack."""
        context = state.get("context", {})
        pack_name = context.get("skill_pack", "research_pack")
        tool_name = context.get("skill_tool") or self._default_tool(pack_name)
        tool_def = self.tool_registry.get(self._tool_key(pack_name, tool_name))
        if not tool_def:
            console.log(f"[red]Unknown tool '{tool_name}' for pack '{pack_name}'[/]")
            return state

        payload = self._collect_payload(state)
        result = self.execute(tool_def, payload)
        append_message(state, "tool", result, name=tool_def.name)
        meta = state.setdefault("metadata", {})
        meta.setdefault("tools", []).append(
            {
                "pack": tool_def.pack,
                "tool": tool_def.name,
                "description": tool_def.description,
            }
        )
        state["output"] = result
        return state

    def _tool_key(self, pack: str, tool_name: str) -> str:
        return f"{pack}.{tool_name}"

    def _default_tool(self, pack_name: str) -> str:
        pack = self.packs.get(pack_name)
        tools = pack.get("tools", []) if pack else []
        return tools[0] if tools else ""

    def _collect_payload(self, state: Dict[str, Any]) -> Any:
        args = state.get("context", {}).get("skill_args")
        if args is None:
            last_message = (state.get("messages") or [{}])[-1]
            args = last_message.get("content")
        return args

    def _filesystem_reader(self, root: Path) -> Callable[..., str]:
        def read_file(path: str = "") -> str:
            target = (root / path).resolve()
            if not str(target).startswith(str(root)):
                return "Access denied."
            if not target.exists():
                return f"File not found: {target}"
            return target.read_text(encoding="utf-8")

        return read_file

    def _mcp_proxy(self, server_name: str, server_type: str) -> Callable[..., str]:
        def proxy(**kwargs: Any) -> str:
            payload = ", ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else "no payload"
            return f"[MCP:{server_name} ({server_type})] would execute with {payload}"

        return proxy
