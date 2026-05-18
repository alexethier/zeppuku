"""host-poc MCP server: small proof-of-concept tools that exercise the host
bridge — `ls` (list a directory) and `env` (show the bridge process's env)."""
from __future__ import annotations

from aethier_mcp_core import create_server, host, run

mcp = create_server("host-poc")


@mcp.tool()
async def ls(path: str) -> str:
    """List files at the given host path. Runs `ls -la <path>` on the host."""
    r = await host.run("ls", "-la", path)
    if r.error:
        raise RuntimeError(f"bridge error: {r.error}")
    if r.exit_code != 0:
        raise RuntimeError(
            f"ls failed (exit {r.exit_code}): {r.stderr.strip()}"
        )
    return r.stdout


@mcp.tool()
async def env() -> str:
    """Print the environment variables visible to the bridge process.

    Runs `env` on the host and returns the full output. Useful for debugging
    PATH / credential issues in other host-bridged MCPs (e.g. when oflowctl
    or snow can't be found, or when a tool can't reach an upstream service).
    """
    r = await host.run("env")
    if r.error:
        raise RuntimeError(f"bridge error: {r.error}")
    if r.exit_code != 0:
        raise RuntimeError(
            f"env failed (exit {r.exit_code}): {r.stderr.strip()}"
        )
    return r.stdout


def main() -> None:
    run(mcp)
