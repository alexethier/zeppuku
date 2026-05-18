"""Host bridge for aethier-mcp containerized MCP servers.

WebSocket server on localhost. Spawns processes on the host on request
and streams stdio + exit code back as JSON frames. No auth: bound to
127.0.0.1 only, not reachable from off-machine.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

import websockets

logging.getLogger("websockets.server").setLevel(logging.CRITICAL)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000

# The bridge daemon is launched via `uv run`, which activates aethier-mcp's
# own .venv. Those activation vars leak into every child process unless we
# scrub them, which breaks tools that do their own venv detection (poetry
# was the canary: it sees VIRTUAL_ENV, defers to it, and imports fail
# because the bridge's venv has none of poetry's project deps).
_VENV_LEAK_VARS = (
    "VIRTUAL_ENV",
    "VIRTUAL_ENV_PROMPT",
    "PYTHONHOME",
    "UV_PROJECT_ENVIRONMENT",
)


def _clean_env(env_overrides: dict) -> dict:
    """Build a child-process env that looks like a normal shell, not like
    we're inside the bridge's own uv-managed venv."""
    env = {k: v for k, v in os.environ.items() if k not in _VENV_LEAK_VARS}

    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        venv_bin = f"{venv}/bin"
        path_parts = env.get("PATH", "").split(os.pathsep)
        env["PATH"] = os.pathsep.join(p for p in path_parts if p != venv_bin)

    env.update(env_overrides)
    return env


async def _stream_pipe(stream, kind: str, ws) -> None:
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return
        text = chunk.decode("utf-8", "replace")
        print(f"[bridge] {kind}: {text.rstrip()}", file=sys.stderr)
        await ws.send(json.dumps({"kind": kind, "data": text}))


async def _handle_spawn(ws, msg: dict) -> None:
    cmd = msg["cmd"]
    args = msg.get("args", [])
    cwd = msg.get("cwd")
    env_overrides = msg.get("env") or {}

    print(f"[bridge] spawn: {cmd} {' '.join(args)}", file=sys.stderr)

    proc = await asyncio.create_subprocess_exec(
        cmd,
        *args,
        cwd=cwd,
        env=_clean_env(env_overrides),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    await asyncio.gather(
        _stream_pipe(proc.stdout, "stdout", ws),
        _stream_pipe(proc.stderr, "stderr", ws),
    )
    rc = await proc.wait()
    await ws.send(json.dumps({"kind": "exit", "code": rc}))


async def _handler(ws) -> None:
    print(f"[bridge] connection from {ws.remote_address}", file=sys.stderr)
    try:
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("op") == "spawn":
                try:
                    await _handle_spawn(ws, msg)
                except FileNotFoundError as e:
                    await ws.send(
                        json.dumps({"kind": "error", "message": f"not found: {e}"})
                    )
                except Exception as e:
                    await ws.send(
                        json.dumps({"kind": "error", "message": str(e)})
                    )
    except websockets.ConnectionClosed:
        pass


async def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Start the bridge. Blocks until cancelled."""
    print(f"[bridge] listening on {host}:{port}", file=sys.stderr)
    async with websockets.serve(_handler, host, port):
        await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aethier-mcp-bridge",
        description="Host bridge daemon for aethier-mcp containerized MCP servers.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("BRIDGE_HOST", DEFAULT_HOST),
        help=f"bind address (default: {DEFAULT_HOST}, env: BRIDGE_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("BRIDGE_PORT", str(DEFAULT_PORT))),
        help=f"bind port (default: {DEFAULT_PORT}, env: BRIDGE_PORT)",
    )
    args = parser.parse_args()
    try:
        asyncio.run(serve(host=args.host, port=args.port))
    except KeyboardInterrupt:
        pass
