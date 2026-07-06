"""Web search MCP server — DuckDuckGo search and page fetch."""

import httpx
from duckduckgo_search import DDGS
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("WebSearch")

MAX_PAGE_CHARS = 8000
CHUNK_SIZE = 2000


@mcp.tool()
def search(query: str, max_results: int = 5) -> str:
    """Search the web via DuckDuckGo and return titles, URLs, and snippets."""
    max_results = max(1, min(10, max_results))
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return f"No results for: {query}"
    lines = [f"Search results for '{query}':"]
    for i, hit in enumerate(results, 1):
        title = hit.get("title", "Untitled")
        url = hit.get("href", hit.get("link", ""))
        body = hit.get("body", hit.get("snippet", ""))
        lines.append(f"\n{i}. {title}\n   URL: {url}\n   {body}")
    return "\n".join(lines)


@mcp.tool()
async def fetch_page(url: str) -> str:
    """Fetch a web page and return truncated plain text (chunked for long pages)."""
    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": "MCP-WebSearch/1.0"},
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type.lower():
            text = _html_to_text(resp.text)
        else:
            text = resp.text

    if len(text) <= MAX_PAGE_CHARS:
        return text

    chunks = [
        text[i : i + CHUNK_SIZE] for i in range(0, min(len(text), MAX_PAGE_CHARS), CHUNK_SIZE)
    ]
    header = f"[Page truncated to {MAX_PAGE_CHARS} chars of {len(text)} total]\n\n"
    return header + "\n---\n".join(chunks)


def _html_to_text(html: str) -> str:
    try:
        from html.parser import HTMLParser

        class _Stripper(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []

            def handle_data(self, data: str) -> None:
                stripped = data.strip()
                if stripped:
                    self.parts.append(stripped)

        parser = _Stripper()
        parser.feed(html)
        return "\n".join(parser.parts)
    except Exception:
        return html[:MAX_PAGE_CHARS]


if __name__ == "__main__":
    mcp.run()
