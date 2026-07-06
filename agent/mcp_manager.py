"""MCP client: spawn servers, discover tools, call tools."""

from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent, Tool

from agent.registry import PROJECT_ROOT, ServerEntry, load_registry


@dataclass
class ToolInfo:
    server_name: str
    tool_name: str
    qualified_name: str
    description: str
    input_schema: dict[str, Any]

    def to_llm_dict(self) -> dict[str, Any]:
        return {
            "qualified_name": self.qualified_name,
            "server": self.server_name,
            "tool": self.tool_name,
            "description": self.description,
            "parameters": self.input_schema,
        }


@dataclass
class ToolResult:
    server_name: str
    tool_name: str
    content: str
    is_error: bool = False


def _stdio_params(entry: ServerEntry) -> StdioServerParameters:
    resolved_args = []
    for arg in entry.args:
        p = Path(arg) if not os.path.isabs(arg) else Path(arg)
        if len(arg) > 0 and arg.endswith(".py") and not os.path.isabs(arg):
            resolved_args.append(str((PROJECT_ROOT / arg).resolve()))
        else:
            resolved_args.append(arg)
    return StdioServerParameters(
        command=entry.command,
        args=resolved_args,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        cwd=str(PROJECT_ROOT),
    )


class MCPMarketplace:
    """Manages MCP server subprocesses and tool calls for one agent run."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self._entries = load_registry(registry_path)
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._active_servers: set[str] = set()
        self.catalog: list[ToolInfo] = []

    async def __aenter__(self) -> MCPMarketplace:
        await self._stack.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._stack.__aexit__(*args)

    async def ensure_server(self, server_name: str) -> ClientSession:
        if server_name in self._sessions:
            return self._sessions[server_name]
        entry = next((e for e in self._entries if e.name == server_name), None)
        if not entry:
            raise ValueError(f"Unknown server: {server_name}")
        read, write = await self._stack.enter_async_context(stdio_client(_stdio_params(entry)))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[server_name] = session
        self._active_servers.add(server_name)
        return session

    async def discover_all(self) -> list[ToolInfo]:
        """Call tools/list on every registered server (marketplace discovery)."""
        self.catalog.clear()

        async def _list_for(entry: ServerEntry) -> list[ToolInfo]:
            session = await self.ensure_server(entry.name)
            response = await session.list_tools()
            return [_tool_to_info(entry.name, tool) for tool in response.tools]

        results = await asyncio.gather(*[_list_for(e) for e in self._entries])
        for tools in results:
            self.catalog.extend(tools)
        return self.catalog

    async def discover_servers(self, server_names: list[str]) -> list[ToolInfo]:
        """Discover tools only from specific servers (lazy spawn)."""
        discovered: list[ToolInfo] = []
        for name in server_names:
            entry = next((e for e in self._entries if e.name == name), None)
            if not entry:
                continue
            session = await self.ensure_server(name)
            response = await session.list_tools()
            for tool in response.tools:
                info = _tool_to_info(name, tool)
                if not any(t.qualified_name == info.qualified_name for t in self.catalog):
                    self.catalog.append(info)
                discovered.append(info)
        return discovered

    def get_tool(self, qualified_name: str) -> ToolInfo | None:
        return next((t for t in self.catalog if t.qualified_name == qualified_name), None)

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> ToolResult:
        session = await self.ensure_server(server_name)
        result = await session.call_tool(tool_name, arguments or {})
        text, is_error = _parse_call_result(result)
        return ToolResult(
            server_name=server_name,
            tool_name=tool_name,
            content=text,
            is_error=is_error,
        )

    async def call_qualified(self, qualified_name: str, arguments: dict[str, Any]) -> ToolResult:
        info = self.get_tool(qualified_name)
        if not info:
            raise ValueError(f"Tool not in catalog: {qualified_name}")
        return await self.call_tool(info.server_name, info.tool_name, arguments)


def _tool_to_info(server_name: str, tool: Tool) -> ToolInfo:
    schema: dict[str, Any] = {}
    if tool.inputSchema:
        schema = dict(tool.inputSchema) if isinstance(tool.inputSchema, dict) else {}
    return ToolInfo(
        server_name=server_name,
        tool_name=tool.name,
        qualified_name=f"{server_name}__{tool.name}",
        description=tool.description or "",
        input_schema=schema,
    )


def _parse_call_result(result: Any) -> tuple[str, bool]:
    parts: list[str] = []
    is_error = getattr(result, "isError", False)
    for block in getattr(result, "content", []) or []:
        if isinstance(block, TextContent):
            parts.append(block.text)
        elif hasattr(block, "text"):
            parts.append(block.text)
        else:
            parts.append(str(block))
    return "\n".join(parts) if parts else "(empty result)", bool(is_error)
