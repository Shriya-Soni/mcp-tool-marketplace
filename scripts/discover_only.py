#!/usr/bin/env python3
"""Minimal discovery client — lists tools from all registered MCP servers."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mcp_manager import MCPMarketplace


async def main() -> None:
    async with MCPMarketplace() as mp:
        catalog = await mp.discover_all()
        print(f"Discovered {len(catalog)} tools:\n")
        for tool in catalog:
            print(f"  {tool.qualified_name}")
            if tool.description:
                print(f"    {tool.description}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
