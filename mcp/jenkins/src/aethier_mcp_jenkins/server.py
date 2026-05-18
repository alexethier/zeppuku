"""jenkins MCP server: read-only Jenkins introspection via REST API.

Talks directly to the Jenkins HTTP API with httpx using basic auth
(JENKINS_USER + JENKINS_TOKEN).
Container env (URL/user/token) is forwarded by bin/manager from the
shell that ran `./bin/manager start jenkins`.
"""
from __future__ import annotations

import os
import re
import time
import urllib.parse

import httpx

from aethier_mcp_core import add_log_fields, create_server, run

mcp = create_server("jenkins")

JENKINS_URL = os.environ["JENKINS_URL"].rstrip("/")
JENKINS_USER = os.environ["JENKINS_USER"]
JENKINS_TOKEN = os.environ["JENKINS_TOKEN"]

JOB_NAME_RE = re.compile(r"^[A-Za-z0-9._%-]+(/[A-Za-z0-9._%-]+)*$")
BUILD_RE = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_TAIL = 50_000
MAX_RUNS = 100

# Two-phase poll timing (all internal — agent has no control).
EARLY_SLEEP_S = 500   # sleep hint before MIN_WAIT_S (agent's max sleep)
LATE_SLEEP_S = 60     # sleep hint after MIN_WAIT_S
MIN_WAIT_S = 1200     # 20 min — builds can't finish before this
MAX_WAIT_S = 3600     # 60 min — hard deadline

MAX_POLL_STATES = 10_000
_poll_state: dict[str, dict] = {}

CLASS_TO_TYPE = {
    "org.jenkinsci.plugins.workflow.job.WorkflowJob": "pipeline",
    "hudson.model.FreeStyleProject": "freestyle",
    "com.cloudbees.hudson.plugins.folder.Folder": "folder",
    "jenkins.branch.OrganizationFolder": "folder",
    "org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject": "multibranch",
}


def _job_path(name: str) -> str:
    """Convert 'a/b/c' to '/job/a/job/b/job/c' with each segment URL-encoded.

    `/` is the path separator between Jenkins folder/job levels. To embed a
    literal `/` inside a single segment (e.g. multibranch branch names like
    `dev/ae-main` which Jenkins represents as `dev%2Fae-main`), pass it
    pre-encoded as `%2F`: `team-builds/dev%2Fmain`. We
    percent-decode each segment then re-encode it with `safe=""`, which
    round-trips correctly and is idempotent.
    """
    parts = []
    for raw in name.split("/"):
        if not raw:
            continue
        decoded = urllib.parse.unquote(raw)
        parts.append(urllib.parse.quote(decoded, safe=""))
    return "/job/" + "/job/".join(parts) if parts else ""


async def _api_get(path: str, *, params: dict | None = None) -> httpx.Response:
    async with httpx.AsyncClient(
        base_url=JENKINS_URL,
        auth=(JENKINS_USER, JENKINS_TOKEN),
        timeout=30.0,
    ) as client:
        resp = await client.get(path, params=params)
    if resp.status_code == 401:
        raise RuntimeError("jenkins rejected credentials (401); check JENKINS_TOKEN")
    if resp.status_code == 404:
        raise RuntimeError(f"not found: {path}")
    if resp.status_code >= 400:
        raise RuntimeError(
            f"GET {path} failed (HTTP {resp.status_code}): {resp.text[:500]}"
        )
    return resp


@mcp.tool()
async def who_am_i() -> dict:
    """Return credential summary (id, full_name, description) for the
    Jenkins user the MCP is authenticated as. Use this as a sanity check."""
    resp = await _api_get(
        "/me/api/json", params={"tree": "fullName,id,description"}
    )
    data = resp.json()
    return {
        "id": data.get("id"),
        "full_name": data.get("fullName"),
        "description": data.get("description"),
    }


@mcp.tool()
async def list_jobs(folder: str = "") -> list[dict]:
    """List jobs at the given folder path (empty string = root). Call usage('list_jobs') for details."""
    if folder and not JOB_NAME_RE.match(folder):
        raise ValueError(
            f"invalid folder {folder!r}: letters, digits, dot, underscore, "
            "hyphen, slash only"
        )
    path = f"{_job_path(folder)}/api/json"
    resp = await _api_get(
        path, params={"tree": "jobs[name,url,color,_class]"}
    )
    jobs = resp.json().get("jobs", []) or []
    return [
        {
            "name": j["name"],
            "url": j.get("url"),
            "color": j.get("color"),
            "type": CLASS_TO_TYPE.get(j.get("_class", ""), j.get("_class", "")),
        }
        for j in jobs
    ]


@mcp.tool()
async def get_job_status(name: str) -> dict:
    """Return runtime status for a job: color, in_queue, last_build. Call usage('get_job_status') for details."""
    if not JOB_NAME_RE.match(name):
        raise ValueError(
            f"invalid job name {name!r}: letters, digits, dot, underscore, "
            "hyphen, slash only"
        )
    path = f"{_job_path(name)}/api/json"
    resp = await _api_get(
        path,
        params={
            "tree": "name,color,inQueue,"
                    "lastBuild[number,result,building,timestamp,duration,url]"
        },
    )
    data = resp.json()
    color = data.get("color") or ""
    last = data.get("lastBuild") or None
    return {
        "name": data.get("name"),
        "color": color or None,
        "running": color.endswith("_anime") or bool(last and last.get("building")),
        "in_queue": bool(data.get("inQueue")),
        "last_build": {
            "number": last["number"],
            "result": last.get("result"),
            "building": last.get("building", False),
            "timestamp_ms": last.get("timestamp"),
            "duration_ms": last.get("duration"),
            "url": last.get("url"),
        } if last else None,
    }


@mcp.tool()
async def list_runs(name: str, limit: int = 20) -> list[dict]:
    """Return recent builds (newest first) for a job. Call usage('list_runs') for details."""
    if not JOB_NAME_RE.match(name):
        raise ValueError(f"invalid job name {name!r}")
    if not (1 <= limit <= MAX_RUNS):
        raise ValueError(f"invalid limit {limit!r}: 1..{MAX_RUNS}")
    path = f"{_job_path(name)}/api/json"
    resp = await _api_get(
        path,
        params={
            "tree": f"builds[number,result,building,timestamp,duration,url]"
                    f"{{,{limit}}}"
        },
    )
    builds = resp.json().get("builds", []) or []
    return [
        {
            "number": b["number"],
            "result": b.get("result"),
            "building": b.get("building", False),
            "timestamp_ms": b.get("timestamp"),
            "duration_ms": b.get("duration"),
            "url": b.get("url"),
        }
        for b in builds
    ]


@mcp.tool()
async def console(name: str, build: str = "lastBuild", tail: int = 500) -> str:
    """Return the console output for a build. Call usage('console') for details."""
    if not JOB_NAME_RE.match(name):
        raise ValueError(f"invalid job name {name!r}")
    if not BUILD_RE.match(build):
        raise ValueError(
            f"invalid build {build!r}: number or permalink word (lastBuild, "
            "lastSuccessfulBuild, lastFailedBuild, ...)"
        )
    if tail != -1 and not (1 <= tail <= MAX_TAIL):
        raise ValueError(
            f"invalid tail {tail!r}: -1 (all) or 1..{MAX_TAIL}"
        )
    path = f"{_job_path(name)}/{urllib.parse.quote(build, safe='')}/consoleText"
    resp = await _api_get(path)
    text = resp.text
    if tail == -1:
        return text
    lines = text.splitlines()
    return "\n".join(lines[-tail:])


# ---------- await_run --------------------------------------------------

async def _get_build(name: str, build_number: int) -> dict | None:
    """Return one specific build's status dict, or None if 404 (deleted
    or rotated out)."""
    path = f"{_job_path(name)}/{build_number}/api/json"
    try:
        resp = await _api_get(
            path,
            params={"tree": "number,result,building,timestamp,duration,url"},
        )
    except RuntimeError as exc:
        if "not found" in str(exc):
            return None
        raise
    return resp.json()


def _build_fields(build: dict | None) -> dict:
    """Extract the standard build fields from a Jenkins API response."""
    b = build or {}
    return {
        "result": b.get("result"),
        "building": bool(b.get("building")),
        "timestamp_ms": b.get("timestamp"),
        "duration_ms": b.get("duration"),
        "url": b.get("url"),
    }


@mcp.tool()
async def await_run(name: str, build_number: int) -> dict:
    """Poll for a specific Jenkins build to finish. Pollable. Call usage('await_run') for details."""
    if not JOB_NAME_RE.match(name):
        raise ValueError(
            f"invalid job name {name!r}: letters, digits, dot, underscore, "
            "hyphen, slash only"
        )
    if build_number < 1:
        raise ValueError(f"invalid build_number {build_number!r}: must be >= 1")

    if len(_poll_state) > MAX_POLL_STATES:
        _poll_state.clear()

    state_key = f"{name}:{build_number}"
    state = _poll_state.get(state_key)
    if state is None:
        state = {"started_at": time.monotonic(), "polls": 0}
        _poll_state[state_key] = state

    state["polls"] += 1
    elapsed_s = int(time.monotonic() - state["started_at"])
    remaining_s = max(0, MAX_WAIT_S - elapsed_s)

    b = await _get_build(name, build_number)
    if b is None:
        _poll_state.pop(state_key, None)
        raise RuntimeError(
            f"run #{build_number} of {name} not found "
            "(wrong build_number, or rotated out of Jenkins build history)"
        )

    bf = _build_fields(b)

    if not b.get("building"):
        polls = state["polls"]
        _poll_state.pop(state_key, None)
        add_log_fields(
            status="completed", result=bf["result"],
            polls=polls, remaining_s=remaining_s,
        )
        return {
            "status": "completed",
            "next_action": (
                "DONE. Branch on `result` (SUCCESS / FAILURE / UNSTABLE / "
                "ABORTED) and proceed."
            ),
            "status_message": f"Build #{build_number} finished: {bf['result']}",
            "name": name,
            "build_number": b.get("number", build_number),
            **bf,
            "sleep_before_retry_s": None,
            "elapsed_s": elapsed_s,
            "remaining_s": remaining_s,
            "polls": polls,
        }

    if remaining_s <= 0:
        polls = state["polls"]
        _poll_state.pop(state_key, None)
        add_log_fields(
            status="deadline_exceeded", result=bf["result"],
            polls=polls, remaining_s=0,
        )
        return {
            "status": "deadline_exceeded",
            "next_action": (
                "DONE (deadline_exceeded). The build is still running; "
                "report this to the user and let them decide whether to "
                "wait longer."
            ),
            "status_message": (
                f"Deadline exceeded after {polls} poll(s); build "
                f"#{build_number} still running"
            ),
            "name": name,
            "build_number": b.get("number", build_number),
            **bf,
            "sleep_before_retry_s": None,
            "elapsed_s": elapsed_s,
            "remaining_s": 0,
            "polls": polls,
        }

    if elapsed_s < MIN_WAIT_S:
        sleep_hint = min(EARLY_SLEEP_S, remaining_s)
    else:
        sleep_hint = min(LATE_SLEEP_S, remaining_s)

    add_log_fields(
        status="in_progress", result=bf["result"],
        polls=state["polls"], remaining_s=remaining_s,
    )
    return {
        "status": "in_progress",
        "next_action": (
            f"Sleep {sleep_hint} seconds, then re-call "
            f"await_run(name={name!r}, build_number={build_number}). "
            f"{remaining_s} s remain."
        ),
        "status_message": f"Build #{build_number} still running",
        "name": name,
        "build_number": b.get("number", build_number),
        **bf,
        "sleep_before_retry_s": sleep_hint,
        "elapsed_s": elapsed_s,
        "remaining_s": remaining_s,
        "polls": state["polls"],
    }


def main() -> None:
    run(mcp)
