"""Rich CLI for the MCP Tool Marketplace agent."""

import asyncio
import os
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from agent.graph import build_graph
from agent.mcp_manager import MCPMarketplace

console = Console()


async def run_agent(query: str, max_iterations: int = 5) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY is not set.[/red]")
        sys.exit(1)

    async with MCPMarketplace() as marketplace:
        graph = build_graph(marketplace)
        result = await graph.ainvoke(
            {
                "user_query": query,
                "max_iterations": max_iterations,
                "messages": [],
            }
        )
        return result.get("final_answer", "No answer produced.")


async def list_tools_only() -> None:
    async with MCPMarketplace() as marketplace:
        catalog = await marketplace.discover_all()
        table = Table(title="MCP Marketplace — Discovered Tools")
        table.add_column("Qualified Name", style="cyan")
        table.add_column("Server")
        table.add_column("Description")
        for t in catalog:
            table.add_row(t.qualified_name, t.server_name, t.description[:80])
        console.print(table)
        console.print(f"\n[green]{len(catalog)} tools[/green] from {len(marketplace._active_servers)} servers")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="MCP Tool Marketplace Agent")
    parser.add_argument("query", nargs="?", help="User question for the agent")
    parser.add_argument("--discover", action="store_true", help="List tools only (no LLM)")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max plan/execute loops")
    args = parser.parse_args()

    if args.discover:
        asyncio.run(list_tools_only())
        return

    if not args.query:
        console.print(Panel(
            "MCP Tool Marketplace\n\n"
            "Examples:\n"
            "  python -m agent.cli --discover\n"
            "  python -m agent.cli \"What is 15% of 240?\"\n"
            "  python -m agent.cli \"Weather in Tokyo\"\n",
            title="Help",
        ))
        sys.exit(0)

    console.print(Panel(f"[bold]{args.query}[/bold]", title="Query"))
    with console.status("[bold green]Running agent..."):
        answer = asyncio.run(run_agent(args.query, args.max_iterations))
    console.print(Panel(Markdown(answer), title="Answer"))


if __name__ == "__main__":
    main()
