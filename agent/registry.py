"""Load server definitions from registry.json."""

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = PROJECT_ROOT / "registry.json"


@dataclass(frozen=True)
class ServerEntry:
    name: str
    description: str
    command: str
    args: list[str]

    @property
    def qualified_tool_prefix(self) -> str:
        return f"{self.name}__"


def load_registry(path: Path | None = None) -> list[ServerEntry]:
    registry_path = path or DEFAULT_REGISTRY
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    return [
        ServerEntry(
            name=s["name"],
            description=s.get("description", ""),
            command=s["command"],
            args=s["args"],
        )
        for s in data.get("servers", [])
    ]
