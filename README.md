# MCP Tool Marketplace

A central agent that **dynamically discovers** and calls MCP servers based on user intent. Adding a fifth server to `registry.json` requires no agent code changes.

## Architecture

```
User message
     ↓
[discover_tools]  → tools/list on all registered servers
     ↓
[plan]            → LLM picks tools and order
     ↓
[execute_tool]    → tools/call on the chosen server
     ↓
[observe]         → loop if more work needed
     ↓
[respond]         → final answer
```

## MCP Servers

| Server | Tools | Notes |
|--------|-------|-------|
| **calculator** | `add`, `subtract`, `multiply`, `evaluate_expression` | Pure logic, no deps |
| **weather** | `get_current`, `get_forecast` | [Open-Meteo](https://open-meteo.com/) (no API key) |
| **filesystem** | `read_file`, `write_file`, `list_directory` | Sandboxed to `./sandbox/` |
| **websearch** | `search`, `fetch_page` | DuckDuckGo + httpx fetch |

## Setup

```bash
cd /path/to/mcp
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=your-key
```

## Build order (how this repo is organized)

1. **Calculator server** — test with MCP Inspector: `mcp dev servers/calculator/server.py`
2. **Discovery script** — `python scripts/discover_only.py`
3. **LangGraph agent** — `python -m agent.cli "your question"`
4. **Other servers** — registered in `registry.json`
5. **Registry** — `registry.json` maps server names → startup commands
6. **Dynamic spawn** — `MCPMarketplace.ensure_server()` starts subprocesses on demand

## Usage

### List all tools (marketplace discovery)

```bash
python scripts/discover_only.py
# or
python -m agent.cli --discover
```

### Run the agent

```bash
python -m agent.cli "What is 127 times 43?"
python -m agent.cli "Current weather in Paris"
python -m agent.cli "List files in the sandbox"
python -m agent.cli "Search for latest Python 3.12 features"
```

### Test a single server (MCP Inspector)

```bash
pip install "mcp[cli]"
mcp dev servers/calculator/server.py
```

In another terminal:

```bash
npx -y @modelcontextprotocol/inspector
```

Connect via stdio to the running dev server.

## Adding a new server

1. Create `servers/myserver/server.py` with FastMCP tools.
2. Add an entry to `registry.json`:

```json
{
  "name": "myserver",
  "description": "What it does",
  "command": "python",
  "args": ["servers/myserver/server.py"]
}
```

3. Run `python scripts/discover_only.py` — the new tools appear automatically.

## Project layout

```
registry.json          # Server registry
sandbox/               # Filesystem server root
servers/
  calculator/server.py
  weather/server.py
  filesystem/server.py
  websearch/server.py
agent/
  registry.py          # Load registry.json
  mcp_manager.py       # Spawn, discover, call
  graph.py             # LangGraph loop
  cli.py               # Rich CLI
scripts/
  discover_only.py     # Minimal discovery test
```

## Requirements

- Python 3.11+
- `ANTHROPIC_API_KEY` for the agent (servers run without it)
