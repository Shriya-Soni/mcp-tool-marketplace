#!/usr/bin/env python3
"""Quick test: call calculator tools via MCP client."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mcp_manager import MCPMarketplace


async def main() -> None:
    async with MCPMarketplace() as mp:
        await mp.discover_all()
        r1 = await mp.call_qualified("calculator__add", {"a": 10, "b": 32})
        r2 = await mp.call_qualified("calculator__evaluate_expression", {"expression": "(100 - 25) * 2"})
        print("add:", r1.content)
        print("eval:", r2.content)


if __name__ == "__main__":
    asyncio.run(main())
