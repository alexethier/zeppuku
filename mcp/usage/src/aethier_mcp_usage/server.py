"""usage MCP server: on-demand detailed usage docs for tools across MCP servers.

Other MCP servers keep their docstrings short (tool selection only) and
point callers here for parameter details, return shapes, and usage patterns.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from aethier_mcp_core import create_server, run

mcp = create_server("usage")

_YAML_PATH = Path(__file__).parent / "usage.yaml"
USAGE: dict[str, str] = yaml.safe_load(_YAML_PATH.read_text())


@mcp.tool()
async def usage(tool_name: str) -> str:
    """Return detailed usage instructions for an MCP tool.

    Call this if another tools usage mentions this tool.
    """
    if tool_name == "all":
        return "\n\n---\n\n".join(
            f"## {name}\n\n{text}" for name, text in USAGE.items()
        )
    text = USAGE.get(tool_name)
    if text is None:
        return f"Unknown tool {tool_name!r}. Available: {', '.join(sorted(USAGE))}"
    return text


def main() -> None:
    run(mcp)
