"""Tool-call logging for aethier-mcp servers.

Every `@mcp.tool()` registered via the `create_server()`-returned FastMCP
instance is auto-wrapped to emit two JSON lines to a shared log file:

  {"ts":..., "mcp":..., "tool":..., "phase":"start", "call_id":..., "args":{...}}
  {"ts":..., "mcp":..., "tool":..., "phase":"end",   "call_id":..., "duration_ms":..., "call_status":"ok"|"error", "error":..., <custom>...}

`call_status` is the middleware's own ok/error verdict for the call (did
the tool raise or not). It is intentionally namespaced away from any
`status` field a tool may want to put in its own return value or log,
so tools are free to use `status` for their own meaning.

Tools can attach arbitrary custom fields to their `phase:"end"` line by
calling `add_log_fields(**fields)` from inside the tool body. Fields
are run through the same truncation/redaction rules as args before
being merged into the end record. Reserved fields the middleware
always sets \u2014 ts, mcp, tool, phase, call_id, duration_ms, call_status,
error \u2014 cannot be overwritten; collisions are silently dropped to
keep the log schema stable. Custom fields also flush on the error
path, so partial progress shows up even when the tool ultimately
raises.

Single growing file at $HOME/.aedev/aethier-mcp/mcp.log (configurable via
AETHIER_MCP_LOG env var). Multi-process appenders are safe on POSIX as
long as each write fits in PIPE_BUF (~4 KB on macOS, ~64 KB on Linux),
which our truncation rules guarantee.

Args are redacted (any field whose name contains 'token', 'password',
'secret', 'auth', or 'key' becomes '<redacted>') and truncated (string
values > 500 chars become '<truncated N/M>' + first 500 chars). Tool
return values are NOT logged automatically (too noisy and too leaky);
use add_log_fields() to surface specific values you care about.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
import uuid
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Any, Callable

# Per-line max size kept well under PIPE_BUF (4 KB on macOS) so concurrent
# appends from multiple MCP containers don't interleave mid-line.
_MAX_VALUE_CHARS = 500
_REDACT_SUBSTRS = ("token", "password", "secret", "auth", "key")

# Reserved keys on the end record that custom fields cannot overwrite.
# Kept frozen so the log schema stays stable even if a tool tries to
# stomp on them.
_RESERVED_END_KEYS = frozenset({
    "ts", "mcp", "tool", "phase", "call_id",
    "duration_ms", "call_status", "error",
})

# Per-call field bag, set by the wrapper before invoking the user
# function and reset after. add_log_fields() mutates whatever bag is
# bound to the current async/sync call.
_current_fields: ContextVar["dict[str, Any] | None"] = ContextVar(
    "aethier_mcp_toollog_current_fields", default=None
)


def _log_path() -> Path:
    """Resolve the log file path. Honors $AETHIER_MCP_LOG override."""
    override = os.environ.get("AETHIER_MCP_LOG")
    if override:
        return Path(override)
    home = Path(os.environ.get("HOME", "/tmp"))
    return home / ".aedev" / "aethier-mcp" / "mcp.log"


def _should_redact(field_name: str) -> bool:
    lowered = field_name.lower()
    return any(s in lowered for s in _REDACT_SUBSTRS)


def _truncate(value: Any) -> Any:
    """Recursively truncate strings and bytes; redact dict keys whose names
    look secret-y. Leaves numbers, bools, None, and small containers alone."""
    if isinstance(value, (bytes, bytearray)):
        s = value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
        return _truncate(s)
    if isinstance(value, str):
        if len(value) > _MAX_VALUE_CHARS:
            return f"<truncated {_MAX_VALUE_CHARS}/{len(value)}> {value[:_MAX_VALUE_CHARS]}"
        return value
    if isinstance(value, dict):
        return {
            k: ("<redacted>" if _should_redact(str(k)) else _truncate(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_truncate(v) for v in value]
    return value


def _redacted_args(sig: inspect.Signature, args: tuple, kwargs: dict) -> dict:
    """Bind args/kwargs back to parameter names, then redact + truncate."""
    try:
        bound = sig.bind_partial(*args, **kwargs)
    except TypeError:
        return {"_unbindable_args": _truncate(list(args)),
                "_unbindable_kwargs": _truncate(dict(kwargs))}
    return {
        name: ("<redacted>" if _should_redact(name) else _truncate(val))
        for name, val in bound.arguments.items()
    }


def _emit(record: dict) -> None:
    """Append one JSON line. Best-effort: never raise into the tool path."""
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, default=str, separators=(",", ":")) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def add_log_fields(**fields: Any) -> None:
    """Attach custom fields to the current tool call's `phase:"end"` log line.

    Safe to call multiple times within one tool call (later wins for
    repeated keys). No-op if called outside a wrapped tool body (e.g.
    at import time, or from a module-level helper invoked outside any
    tool). Reserved keys (`ts`, `mcp`, `tool`, `phase`, `call_id`,
    `duration_ms`, `call_status`, `error`) are silently dropped to
    keep the log schema stable. Field values are redacted/truncated
    using the same rules as args.

    Example, from inside a tool body:

        from aethier_mcp_core import add_log_fields
        add_log_fields(status="completed", marker_key=key, polls=polls)
    """
    bag = _current_fields.get()
    if bag is None:
        return
    safe = {
        k: ("<redacted>" if _should_redact(str(k)) else _truncate(v))
        for k, v in fields.items()
        if k not in _RESERVED_END_KEYS
    }
    bag.update(safe)


def wrap_tool(func: Callable, *, mcp_name: str) -> Callable:
    """Return a logging wrapper around `func` that preserves async/sync shape
    and inspect.Signature (so FastMCP's schema generation still works)."""
    sig = inspect.signature(func)
    is_coro = asyncio.iscoroutinefunction(func)

    def _start_record(call_id: str, args: tuple, kwargs: dict) -> dict:
        return {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mcp": mcp_name, "tool": func.__name__,
            "phase": "start", "call_id": call_id,
            "args": _redacted_args(sig, args, kwargs),
        }

    def _end_record(
        call_id: str, t0: float, *, call_status: str,
        error: str | None, bag: "dict[str, Any]",
    ) -> dict:
        rec: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mcp": mcp_name, "tool": func.__name__,
            "phase": "end", "call_id": call_id,
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "call_status": call_status,
        }
        if error is not None:
            rec["error"] = error
        for k, v in bag.items():
            if k not in _RESERVED_END_KEYS:
                rec[k] = v
        return rec

    if is_coro:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            call_id = uuid.uuid4().hex[:8]
            t0 = time.monotonic()
            bag: dict[str, Any] = {}
            token = _current_fields.set(bag)
            _emit(_start_record(call_id, args, kwargs))
            try:
                result = await func(*args, **kwargs)
            except BaseException as exc:
                _emit(_end_record(
                    call_id, t0, call_status="error",
                    error=f"{type(exc).__name__}: {exc}"[:_MAX_VALUE_CHARS],
                    bag=bag,
                ))
                _current_fields.reset(token)
                raise
            _emit(_end_record(
                call_id, t0, call_status="ok", error=None, bag=bag,
            ))
            _current_fields.reset(token)
            return result
        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        call_id = uuid.uuid4().hex[:8]
        t0 = time.monotonic()
        bag: dict[str, Any] = {}
        token = _current_fields.set(bag)
        _emit(_start_record(call_id, args, kwargs))
        try:
            result = func(*args, **kwargs)
        except BaseException as exc:
            _emit(_end_record(
                call_id, t0, call_status="error",
                error=f"{type(exc).__name__}: {exc}"[:_MAX_VALUE_CHARS],
                bag=bag,
            ))
            _current_fields.reset(token)
            raise
        _emit(_end_record(
            call_id, t0, call_status="ok", error=None, bag=bag,
        ))
        _current_fields.reset(token)
        return result
    return sync_wrapper


def install(mcp: Any, mcp_name: str) -> None:
    """Monkey-patch `mcp.tool` so every subsequent @mcp.tool() registration
    wraps the user function with our logger before handing it to FastMCP."""
    original_tool = mcp.tool

    def patched_tool(*tool_args: Any, **tool_kwargs: Any) -> Callable:
        decorator = original_tool(*tool_args, **tool_kwargs)
        def wrapping_decorator(func: Callable) -> Callable:
            wrapped = wrap_tool(func, mcp_name=mcp_name)
            return decorator(wrapped)
        return wrapping_decorator

    mcp.tool = patched_tool
