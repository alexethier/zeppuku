"""jira MCP server: read-only Jira Cloud access via REST API.

Talks directly to a Jira Cloud site (e.g. example.atlassian.net)
with httpx using basic auth (ATLASSIAN_EMAIL + ATLASSIAN_TOKEN, where the
token is an Atlassian Cloud API token from id.atlassian.com). No OAuth
3LO, no host bridge. Container env is forwarded by bin/manager from the
shell that ran `./bin/manager start jira`.

Uses the post-deprecation /rest/api/3/search/jql endpoint, which requires
every query to be bounded by project, key, assignee, or a date range.
search_issues() injects `project = $JIRA_DEFAULT_PROJECT AND` automatically
when the user-supplied JQL has no bounding clause.
"""
from __future__ import annotations

import os
import re

import httpx

from aethier_mcp_core import create_server, host, run

mcp = create_server("jira")

JIRA_BASE_URL = os.environ["JIRA_BASE_URL"].rstrip("/")
ATLASSIAN_EMAIL = os.environ["ATLASSIAN_EMAIL"]
ATLASSIAN_TOKEN = os.environ["ATLASSIAN_TOKEN"]
JIRA_DEFAULT_PROJECT = os.environ.get("JIRA_DEFAULT_PROJECT", "FLOW")

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")
PROJECT_RE = re.compile(r"^[A-Z][A-Z0-9_]+$")
MAX_LIMIT = 50
MAX_PROJECT_LIMIT = 100
MAX_COMMENTS = 50
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_JQL_LEN = 2000

VALID_FORMATS = {"text", "html"}

# Bounding-clause detector: Jira's /search/jql rejects "unbounded" queries
# (no project / key / user / time filter). Match any of these clauses
# anywhere in the JQL to decide whether we need to inject `project = X AND`.
_BOUNDING_RE = re.compile(
    r"\b("
    r"project\s*(=|in\b|!=)"
    r"|key\s*(=|in\b|!=)"
    r"|issuekey\s*(=|in\b|!=)"
    r"|assignee\s*(=|in\b|!=|was\b)"
    r"|reporter\s*(=|in\b|!=|was\b)"
    r"|creator\s*(=|in\b|!=)"
    r"|created\s*[><=]"
    r"|updated\s*[><=]"
    r"|due\s*[><=]"
    r"|resolved\s*[><=]"
    r")",
    re.IGNORECASE,
)
_ORDER_BY_RE = re.compile(r"\border\s+by\b", re.IGNORECASE)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n{3,}")

CLASS_TO_TYPE = {
    "software": "software",
    "service_desk": "service_desk",
    "business": "business",
}


def _strip_html(html: str) -> str:
    """Best-effort HTML -> plain text. Not a real parser; good enough
    for terminal/LLM consumption of Jira renderedFields HTML."""
    import html as html_mod

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    text = html_mod.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = _BLANK_RE.sub("\n\n", text)
    return text.strip()


def _jql_escape(value: str) -> str:
    """Escape a value for inclusion in a JQL string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _has_bounding_clause(jql: str) -> bool:
    """Return True if `jql` contains at least one clause that satisfies
    Jira's /search/jql bounding requirement (project, key, assignee,
    reporter, creator, or a created/updated/due/resolved date filter)."""
    return bool(_BOUNDING_RE.search(jql))


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=JIRA_BASE_URL,
        auth=(ATLASSIAN_EMAIL, ATLASSIAN_TOKEN),
        timeout=30.0,
        headers={"Accept": "application/json"},
    )


def _check_response(resp: httpx.Response, method: str, path: str) -> None:
    if resp.status_code == 401:
        raise RuntimeError(
            "jira rejected credentials (401); check ATLASSIAN_EMAIL "
            "and ATLASSIAN_TOKEN"
        )
    if resp.status_code == 403:
        raise RuntimeError(f"forbidden: {path} (your account lacks permission)")
    if resp.status_code == 404:
        raise RuntimeError(f"not found: {path}")
    if resp.status_code >= 400:
        raise RuntimeError(
            f"{method} {path} failed (HTTP {resp.status_code}): {resp.text[:500]}"
        )


async def _api_get(path: str, *, params: dict | None = None) -> httpx.Response:
    async with _client() as client:
        resp = await client.get(path, params=params)
    _check_response(resp, "GET", path)
    return resp


async def _api_post(path: str, *, json: dict | None = None) -> httpx.Response:
    async with _client() as client:
        resp = await client.post(path, json=json)
    _check_response(resp, "POST", path)
    return resp


async def _api_put(path: str, *, json: dict | None = None) -> httpx.Response:
    async with _client() as client:
        resp = await client.put(path, json=json)
    _check_response(resp, "PUT", path)
    return resp


def _issue_url(key: str) -> str:
    return f"{JIRA_BASE_URL}/browse/{key}"


@mcp.tool()
async def who_am_i() -> dict:
    """Return account summary (account_id, email, display_name, time_zone)
    for the Jira user the MCP is authenticated as. Use this as a sanity check."""
    resp = await _api_get("/rest/api/3/myself")
    data = resp.json()
    return {
        "account_id": data.get("accountId"),
        "email": data.get("emailAddress"),
        "display_name": data.get("displayName"),
        "account_type": data.get("accountType"),
        "time_zone": data.get("timeZone"),
        "locale": data.get("locale"),
    }


@mcp.tool()
async def list_projects(limit: int = 50) -> list[dict]:
    """List Jira projects you can see. Call usage('list_projects') for details."""
    if not (1 <= limit <= MAX_PROJECT_LIMIT):
        raise ValueError(f"invalid limit {limit!r}: 1..{MAX_PROJECT_LIMIT}")

    resp = await _api_get(
        "/rest/api/3/project/search", params={"maxResults": limit}
    )
    values = resp.json().get("values", []) or []
    out: list[dict] = []
    for p in values:
        ptype = p.get("projectTypeKey", "")
        out.append(
            {
                "key": p.get("key"),
                "name": p.get("name"),
                "type": CLASS_TO_TYPE.get(ptype, ptype),
                "url": f"{JIRA_BASE_URL}/projects/{p.get('key')}" if p.get("key") else None,
            }
        )
    return out


@mcp.tool()
async def search_issues(
    jql: str = "", project: str = "", limit: int = 10
) -> list[dict]:
    """Search Jira issues with JQL. Call usage('search_issues') for details."""
    if len(jql) > MAX_JQL_LEN:
        raise ValueError(f"jql too long: max {MAX_JQL_LEN} chars")
    if project and not PROJECT_RE.match(project):
        raise ValueError(
            f"invalid project {project!r}: uppercase letters, digits, "
            "underscore only (e.g. FLOW, SNOW)"
        )
    if not (1 <= limit <= MAX_LIMIT):
        raise ValueError(f"invalid limit {limit!r}: 1..{MAX_LIMIT}")

    effective_project = project or JIRA_DEFAULT_PROJECT
    jql = jql.strip()
    if not jql:
        effective_jql = (
            f'project = "{_jql_escape(effective_project)}" ORDER BY updated DESC'
        )
    elif _has_bounding_clause(jql):
        effective_jql = jql
    else:
        prefix = f'project = "{_jql_escape(effective_project)}" AND '
        suffix = "" if _ORDER_BY_RE.search(jql) else " ORDER BY updated DESC"
        effective_jql = f"{prefix}{jql}{suffix}"

    try:
        resp = await _api_get(
            "/rest/api/3/search/jql",
            params={
                "jql": effective_jql,
                "maxResults": limit,
                "fields": "summary,status,priority,assignee,reporter,updated",
            },
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "Unbounded JQL" in msg or "unbounded" in msg.lower():
            raise RuntimeError(
                "jira rejected the query as unbounded. Add a bounding clause "
                "to your jql (e.g. `project = FLOW`, `assignee = currentUser()`, "
                "or `updated >= -30d`), or pass `project=<KEY>` to search_issues."
            ) from exc
        raise

    issues = resp.json().get("issues", []) or []
    out: list[dict] = []
    for issue in issues:
        fields = issue.get("fields") or {}
        status = (fields.get("status") or {}).get("name")
        priority = (fields.get("priority") or {}).get("name")
        assignee = (fields.get("assignee") or {}).get("displayName")
        reporter = (fields.get("reporter") or {}).get("displayName")
        key = issue.get("key")
        out.append(
            {
                "key": key,
                "summary": fields.get("summary"),
                "status": status,
                "priority": priority,
                "assignee": assignee,
                "reporter": reporter,
                "updated": fields.get("updated"),
                "url": _issue_url(key) if key else None,
            }
        )
    return out


@mcp.tool()
async def read_issue(key: str, format: str = "text") -> dict:
    """Read a single Jira issue by key, including comments. Call usage('read_issue') for details."""
    if not KEY_RE.match(key):
        raise ValueError(
            f"invalid key {key!r}: format is PROJECT-NUMBER (e.g. FLOW-10705)"
        )
    if format not in VALID_FORMATS:
        raise ValueError(
            f"invalid format {format!r}: one of {sorted(VALID_FORMATS)}"
        )

    issue_resp = await _api_get(
        f"/rest/api/3/issue/{key}",
        params={
            "fields": "summary,status,priority,assignee,reporter,labels,created,updated,description",
            "expand": "renderedFields",
        },
    )
    data = issue_resp.json()
    fields = data.get("fields") or {}
    rendered = data.get("renderedFields") or {}

    description_html = rendered.get("description") or ""
    description = (
        _strip_html(description_html) if format == "text" else description_html
    )

    comments_resp = await _api_get(
        f"/rest/api/3/issue/{key}/comment",
        params={"expand": "renderedBody", "maxResults": MAX_COMMENTS},
    )
    raw_comments = comments_resp.json().get("comments", []) or []
    comments: list[dict] = []
    for c in raw_comments:
        body_html = c.get("renderedBody") or ""
        body = _strip_html(body_html) if format == "text" else body_html
        comments.append(
            {
                "comment_id": c.get("id"),
                "author": (c.get("author") or {}).get("displayName"),
                "created": c.get("created"),
                "updated": c.get("updated"),
                "body": body,
            }
        )

    return {
        "key": data.get("key"),
        "summary": fields.get("summary"),
        "status": (fields.get("status") or {}).get("name"),
        "priority": (fields.get("priority") or {}).get("name"),
        "assignee": (fields.get("assignee") or {}).get("displayName"),
        "reporter": (fields.get("reporter") or {}).get("displayName"),
        "labels": fields.get("labels") or [],
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "url": _issue_url(data.get("key")) if data.get("key") else None,
        "format": format,
        "description": description,
        "comments": comments,
    }


@mcp.tool()
async def comment(key: str, body: str, comment_id: str = "") -> dict:
    """Create or update a comment on a Jira issue. Call usage('comment') for details."""
    if not KEY_RE.match(key):
        raise ValueError(
            f"invalid key {key!r}: format is PROJECT-NUMBER (e.g. FLOW-10705)"
        )
    if not body or not body.strip():
        raise ValueError("body must be non-empty")

    adf_body = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": body}],
            }
        ],
    }

    if comment_id:
        resp = await _api_put(
            f"/rest/api/3/issue/{key}/comment/{comment_id}",
            json={"body": adf_body},
        )
    else:
        resp = await _api_post(
            f"/rest/api/3/issue/{key}/comment",
            json={"body": adf_body},
        )
    data = resp.json()
    return {
        "key": key,
        "comment_id": data.get("id"),
        "author": (data.get("author") or {}).get("displayName"),
        "created": data.get("created"),
        "body": body,
    }


@mcp.tool()
async def transition(key: str, status: str) -> dict:
    """Transition a Jira issue to a new status. Call usage('transition') for details."""
    if not KEY_RE.match(key):
        raise ValueError(
            f"invalid key {key!r}: format is PROJECT-NUMBER (e.g. FLOW-10705)"
        )
    if not status or not status.strip():
        raise ValueError("status must be non-empty")

    resp = await _api_get(f"/rest/api/3/issue/{key}/transitions")
    transitions = resp.json().get("transitions", []) or []
    if not transitions:
        raise RuntimeError(f"no transitions available for {key}")

    needle = status.strip().lower()
    match = next(
        (t for t in transitions if needle in t.get("name", "").lower()),
        None,
    )
    if match is None:
        available = [t.get("name") for t in transitions]
        raise ValueError(
            f"no transition matching {status!r} for {key}. "
            f"Available: {available}"
        )

    await _api_post(
        f"/rest/api/3/issue/{key}/transitions",
        json={"transition": {"id": match["id"]}},
    )
    return {
        "key": key,
        "transition_id": match["id"],
        "transition_name": match["name"],
    }


@mcp.tool()
async def attach_file(key: str, file_path: str) -> dict:
    """Attach a host file to a Jira issue. Call usage('attach_file') for details."""
    import base64
    import posixpath

    if not KEY_RE.match(key):
        raise ValueError(
            f"invalid key {key!r}: format is PROJECT-NUMBER (e.g. FLOW-10705)"
        )

    # Verify the file exists on the host and check its size
    stat = await host.run("stat", "-f", "%z", file_path)
    if stat.error:
        raise RuntimeError(f"bridge error checking file: {stat.error}")
    if stat.exit_code != 0:
        raise ValueError(f"file not found on host: {file_path}")
    file_size = int(stat.stdout.strip())
    if file_size > MAX_ATTACHMENT_BYTES:
        raise ValueError(
            f"file too large: {file_size} bytes "
            f"(limit is {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB)"
        )

    # Read the file as base64 via the bridge
    b64 = await host.run("base64", "-i", file_path)
    if b64.error:
        raise RuntimeError(f"bridge error reading file: {b64.error}")
    if b64.exit_code != 0:
        raise RuntimeError(
            f"base64 {file_path} failed (exit {b64.exit_code}): {b64.stderr.strip()}"
        )

    content = base64.b64decode(b64.stdout)
    filename = posixpath.basename(file_path.rstrip("/"))

    async with httpx.AsyncClient(
        base_url=JIRA_BASE_URL,
        auth=(ATLASSIAN_EMAIL, ATLASSIAN_TOKEN),
        timeout=60.0,
        headers={"X-Atlassian-Token": "no-check"},
    ) as client:
        resp = await client.post(
            f"/rest/api/3/issue/{key}/attachments",
            files={"file": (filename, content)},
        )
    _check_response(resp, "POST", f"/rest/api/3/issue/{key}/attachments")

    attachments = resp.json()
    if not attachments:
        raise RuntimeError("upload succeeded but no attachment returned")
    att = attachments[0]
    return {
        "key": key,
        "attachment_id": att.get("id"),
        "filename": att.get("filename"),
        "size": att.get("size"),
        "mime_type": att.get("mimeType"),
        "url": att.get("content"),
    }


def main() -> None:
    run(mcp)
