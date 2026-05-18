# aethier-mcp-core

Shared infrastructure for aethier-mcp MCP servers. `host` is the async
client for the host bridge — `await host.run("git", "status")` from
inside a containerized MCP runs the command on the host.
`create_server(name)` returns a configured `FastMCP` bound from
`MCP_HOST` / `MCP_PORT` env vars (defaults `0.0.0.0:8000`), and
`run(mcp)` runs it with Streamable HTTP transport. The bridge URL
defaults to `ws://host.docker.internal:9000` (override with `BRIDGE_URL`).

```python
from aethier_mcp_core import create_server, host, run

mcp = create_server("my-agent")

@mcp.tool()
async def some_tool() -> str:
    r = await host.run("uname", "-a")
    return r.stdout

def main() -> None:
    run(mcp)
```
