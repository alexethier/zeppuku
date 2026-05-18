"""Generic csvq adapter executed on host via the MCP bridge."""
from __future__ import annotations

import json

try:
    from aethier_mcp_core import host
except ModuleNotFoundError:  # pragma: no cover - local unit tests may run without core package
    host = None

_HOST_SCRIPT = r"""
import contextlib
import csv
import fcntl
import json
import os
import subprocess
import sys

payload = json.loads(sys.argv[1])
cmd = payload["cmd"]
root = payload["root"]
lock_path = payload.get("lock_path")


def _run_csvq(query: str) -> list[dict]:
    args = ["csvq", "-q", "-r", root, "--format", "JSONL", query]
    proc = subprocess.run(args, text=True, capture_output=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"csvq failed (exit {proc.returncode}): {detail}")
    rows = []
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _ensure_csv_schema(csv_path: str, expected_headers: list[str]) -> None:
    parent = os.path.dirname(csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if not os.path.exists(csv_path):
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(expected_headers)

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
    if header != expected_headers:
        raise RuntimeError(
            f"invalid schema in {csv_path}: expected {expected_headers}, got {header}"
        )


@contextlib.contextmanager
def _lock():
    if not lock_path:
        raise RuntimeError("lock_path is required for execute()")
    parent = os.path.dirname(lock_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    with os.fdopen(fd, "r+") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


try:
    if cmd == "ensure_csv_schema":
        _ensure_csv_schema(
            payload["csv_path"],
            payload["expected_headers"],
        )
        out = {"ok": True}
    elif cmd == "execute":
        with _lock():
            rows = _run_csvq(payload["query"])
        out = {"rows": rows}
    else:
        raise ValueError(f"unknown cmd: {cmd}")
    print(json.dumps(out))
except Exception as exc:
    print(str(exc), file=sys.stderr)
    raise
"""


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class CsvqHostAdapter:
    """Generic csvq bridge adapter for host-backed CSV storage."""

    def __init__(self, *, root: str, lock_path: str) -> None:
        self._root = root
        self._lock_path = lock_path

    async def _host_call(self, cmd: str, extra: dict | None = None) -> dict:
        if host is None:
            raise RuntimeError("aethier_mcp_core is required to call host bridge operations")

        payload = {
            "cmd": cmd,
            "root": self._root,
            "lock_path": self._lock_path,
        }
        if extra:
            payload.update(extra)

        result = await host.run("python3", "-c", _HOST_SCRIPT, json.dumps(payload))
        if result.error:
            raise RuntimeError(f"bridge error during {cmd}: {result.error}")
        if result.exit_code != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"{cmd} failed (exit {result.exit_code}): {detail}")
        try:
            return json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{cmd} returned invalid JSON: {exc}") from exc

    async def ensure_csv_schema(self, *, csv_path: str, expected_headers: list[str]) -> None:
        await self._host_call(
            "ensure_csv_schema",
            {"csv_path": csv_path, "expected_headers": expected_headers},
        )

    async def execute(self, query: str) -> list[dict]:
        out = await self._host_call("execute", {"query": query})
        return out.get("rows", [])
