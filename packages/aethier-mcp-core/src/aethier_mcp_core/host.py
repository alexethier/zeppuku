"""Async client for the aethier-mcp host bridge.

Containerized agents call `await host.run("git", "status")` and the command
runs on the host (via `host.docker.internal`), with stdout/stderr/exit
streamed back over a WebSocket.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import websockets

BRIDGE_URL = os.environ.get("BRIDGE_URL", "ws://host.docker.internal:9000")


@dataclass
class HostResult:
    exit_code: int | None
    stdout: str
    stderr: str
    error: str | None = None


async def run(
    cmd: str,
    *args: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    bridge_url: str | None = None,
) -> HostResult:
    """Run a command on the host. Returns when the process exits.

    Raises on transport errors (bridge unreachable, etc.). Tool failures
    show up as a non-zero `exit_code` with `stderr` populated, not exceptions.
    """
    url = bridge_url or BRIDGE_URL
    msg: dict = {"op": "spawn", "cmd": cmd, "args": list(args)}
    if cwd is not None:
        msg["cwd"] = cwd
    if env is not None:
        msg["env"] = env

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    exit_code: int | None = None
    error: str | None = None

    async with websockets.connect(url) as ws:
        await ws.send(json.dumps(msg))
        async for raw in ws:
            frame = json.loads(raw)
            kind = frame.get("kind")
            if kind == "stdout":
                stdout_parts.append(frame.get("data", ""))
            elif kind == "stderr":
                stderr_parts.append(frame.get("data", ""))
            elif kind == "exit":
                exit_code = frame.get("code")
                break
            elif kind == "error":
                error = frame.get("message", "unknown bridge error")
                break

    return HostResult(
        exit_code=exit_code,
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
        error=error,
    )
