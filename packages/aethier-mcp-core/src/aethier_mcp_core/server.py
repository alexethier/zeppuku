"""MCP server bootstrap for aethier-mcp servers.

Hides the FastMCP construction (host/port from env) and the transport
choice (Streamable HTTP) so server code is just tools + a one-line `main`.
"""
from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import toollog


def create_server(name: str, **kwargs: Any) -> FastMCP:
    """Build a FastMCP bound to MCP_HOST:MCP_PORT (default 0.0.0.0:8000).

    Also installs the shared tool-call logger; every @mcp.tool() registered
    on the returned server auto-emits start/end JSON events to mcp.log.
    Disable by setting AETHIER_MCP_LOG_DISABLE=1 in the container env.
    """
    mcp = FastMCP(
        name,
        host=os.environ.get("MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_PORT", "8000")),
        **kwargs,
    )
    if not os.environ.get("AETHIER_MCP_LOG_DISABLE"):
        toollog.install(mcp, mcp_name=name)
    return mcp


def run(mcp: FastMCP) -> None:
    """Run the MCP server with Streamable HTTP transport."""
    mcp.run(transport="streamable-http")
