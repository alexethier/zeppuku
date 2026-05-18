"""Host-filesystem helpers for ai-datastore note content files."""
from __future__ import annotations

import json

from aethier_mcp_core import host

from .db import DATASTORE_ROOT
from .validators import ALLOWED_SOURCE_ROOT, slugify_filename_hint, slugify_note_name

_HOST_FS_SCRIPT = r"""
import json
import os
from pathlib import Path
import sys
import uuid

payload = json.loads(sys.argv[1])
action = payload["action"]
root = Path(payload["root"]).expanduser().resolve()
allowed_source_root = Path(payload["allowed_source_root"]).expanduser().resolve()

def _is_within(path: Path, base: Path) -> bool:
    return path == base or str(path).startswith(str(base) + os.sep)

def _safe_rel_path(rel_path: str) -> Path:
    p = (root / rel_path).resolve()
    if not _is_within(p, root):
        raise ValueError(f"path escapes datastore root: {rel_path}")
    return p

os.makedirs(root, exist_ok=True)

if action == "write_note":
    rel_path = payload["rel_path"]
    content = payload["content"]
    abs_path = _safe_rel_path(rel_path)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = abs_path.with_name(f".{abs_path.name}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, abs_path)
    print(json.dumps({"rel_path": rel_path, "abs_path": str(abs_path)}))
elif action == "read_source":
    raw = payload["file_path"]
    source_path = Path(raw).expanduser().resolve()
    if not _is_within(source_path, allowed_source_root):
        raise ValueError(
            f"file_path must be under {allowed_source_root}; got {source_path}"
        )
    if not source_path.exists():
        raise FileNotFoundError(f"file not found: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"path is not a file: {source_path}")
    text = source_path.read_text(encoding="utf-8")
    print(json.dumps({"content": text, "source_path": str(source_path)}))
elif action == "read_rel":
    rel_path = payload["rel_path"]
    abs_path = _safe_rel_path(rel_path)
    if not abs_path.exists():
        raise FileNotFoundError(f"note file not found: {abs_path}")
    if not abs_path.is_file():
        raise ValueError(f"path is not a file: {abs_path}")
    text = abs_path.read_text(encoding="utf-8")
    print(json.dumps({"content": text, "abs_path": str(abs_path)}))
elif action == "delete_rel":
    rel_path = payload["rel_path"]
    abs_path = _safe_rel_path(rel_path)
    existed = abs_path.exists()
    if existed and abs_path.is_file():
        abs_path.unlink()
    print(json.dumps({"deleted": bool(existed)}))
elif action == "remove_workflow_dir_if_empty":
    workflow_id = payload["workflow_id"]
    wf = _safe_rel_path(workflow_id)
    removed = False
    if wf.exists() and wf.is_dir():
        try:
            next(wf.iterdir())
        except StopIteration:
            wf.rmdir()
            removed = True
    print(json.dumps({"removed": removed}))
else:
    raise ValueError(f"unknown filesystem action: {action}")
"""


async def _host_fs_call(action: str, extra: dict | None = None) -> dict:
    payload = {
        "action": action,
        "root": DATASTORE_ROOT,
        "allowed_source_root": str(ALLOWED_SOURCE_ROOT),
    }
    if extra:
        payload.update(extra)
    r = await host.run("python3", "-c", _HOST_FS_SCRIPT, json.dumps(payload))
    if r.error:
        raise RuntimeError(f"bridge error during fs op {action}: {r.error}")
    if r.exit_code != 0:
        detail = (r.stderr or r.stdout).strip()
        raise RuntimeError(f"fs op {action} failed (exit {r.exit_code}): {detail}")
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"fs op {action} returned invalid JSON: {exc}") from exc


async def write_note_content(workflow_id: str, note_id: str, content: str) -> str:
    return await write_note_content_at_path(f"{workflow_id}/{note_id}.md", content)


def build_note_rel_path(
    workflow_id: str,
    note_id: str,
    name: str,
    filename_hint: str | None = None,
) -> str:
    filename = f"{note_id}--{slugify_note_name(name)}"
    if filename_hint is not None:
        filename = f"{filename}--{slugify_filename_hint(filename_hint)}"
    filename = f"{filename}.md"
    return f"{workflow_id}/{filename}"


async def write_note_content_at_path(rel_path: str, content: str) -> str:
    out = await _host_fs_call(
        "write_note",
        {
            "rel_path": rel_path,
            "content": content,
        },
    )
    return str(out["rel_path"])


async def read_source_content(file_path: str) -> str:
    out = await _host_fs_call("read_source", {"file_path": file_path})
    return str(out["content"])


async def read_note_content_at_path(rel_path: str) -> str:
    out = await _host_fs_call("read_rel", {"rel_path": rel_path})
    return str(out["content"])


async def delete_relative_path(rel_path: str) -> bool:
    out = await _host_fs_call("delete_rel", {"rel_path": rel_path})
    return bool(out.get("deleted", False))


async def remove_workflow_dir_if_empty(workflow_id: str) -> bool:
    out = await _host_fs_call(
        "remove_workflow_dir_if_empty",
        {"workflow_id": workflow_id},
    )
    return bool(out.get("removed", False))
