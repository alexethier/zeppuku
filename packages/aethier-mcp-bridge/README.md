# aethier-mcp-bridge

Host-side daemon that lets containerized MCPs execute commands on the
host by exposing a small WebSocket API on `127.0.0.1` (no auth —
localhost-only). Containers reach it at `ws://host.docker.internal:<port>`
(Docker Desktop / OrbStack / Apple Container all forward localhost via
that name). Wire protocol is one JSON request frame per `spawn` (`{op,
cmd, args, cwd?, env?}`) followed by a stream of stdout/stderr/exit/error
event frames; spawns over a single connection are sequential (no
per-spawn handle IDs in v0.1, so no concurrent spawns, no orphan
cleanup, no PTY/TTY, no persistent shell sessions yet). Install with
`uv pip install -e packages/aethier-mcp-bridge` (dev) or
`uv tool install ./packages/aethier-mcp-bridge`; run with
`aethier-mcp-bridge` (defaults `127.0.0.1:9000`, override with
`--port` or `BRIDGE_PORT`).

```bash
aethier-mcp-bridge          # 127.0.0.1:9000
```
