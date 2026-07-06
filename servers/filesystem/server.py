"""Filesystem MCP server — sandboxed read/write/list."""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Filesystem")

_ROOT = Path(__file__).resolve().parents[2] / "sandbox"
_ROOT.mkdir(parents=True, exist_ok=True)


def _resolve_safe(path: str) -> Path:
    """Resolve path within sandbox; reject path traversal."""
    candidate = (_ROOT / path).resolve()
    if not str(candidate).startswith(str(_ROOT.resolve())):
        raise ValueError(f"Path escapes sandbox: {path}")
    return candidate


@mcp.tool()
def read_file(path: str) -> str:
    """Read a file from the sandbox directory."""
    target = _resolve_safe(path)
    if not target.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    return target.read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file in the sandbox (creates parent dirs)."""
    target = _resolve_safe(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {path}"


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List files and directories in a sandbox path."""
    target = _resolve_safe(path)
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    lines = [f"Contents of {path or '.'} (sandbox root: {_ROOT}):"]
    for entry in entries:
        kind = "dir" if entry.is_dir() else "file"
        size = entry.stat().st_size if entry.is_file() else ""
        suffix = f" ({size} bytes)" if size != "" else ""
        rel = entry.relative_to(_ROOT)
        lines.append(f"  [{kind}] {rel}{suffix}")
    if len(lines) == 1:
        lines.append("  (empty)")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
