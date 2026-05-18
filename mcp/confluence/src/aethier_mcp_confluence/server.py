"""confluence MCP server: read-only Confluence Cloud access via REST API.

Talks directly to a Confluence Cloud site (e.g. example.atlassian.net/wiki)
with httpx using basic auth (ATLASSIAN_EMAIL + ATLASSIAN_TOKEN, where the
token is an Atlassian Cloud API token from id.atlassian.com). No OAuth
3LO, no host bridge. Container env is forwarded by bin/manager from the
shell that ran `./bin/manager start confluence`.
"""
from __future__ import annotations

import os
import re

import httpx

from aethier_mcp_core import create_server, run

mcp = create_server("confluence")

CONFLUENCE_BASE_URL = os.environ["CONFLUENCE_BASE_URL"].rstrip("/")
ATLASSIAN_EMAIL = os.environ["ATLASSIAN_EMAIL"]
ATLASSIAN_TOKEN = os.environ["ATLASSIAN_TOKEN"]

PAGE_ID_RE = re.compile(r"^[0-9]+$")
SPACE_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
MAX_LIMIT = 50
MAX_QUERY_LEN = 500

VALID_FORMATS = {"text", "storage", "view"}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n{3,}")


def _strip_html(html: str) -> str:
    """Best-effort HTML/storage -> plain text. Not a real parser; good enough
    for terminal/LLM consumption of Confluence body.view or body.storage."""
    import html as html_mod

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    text = html_mod.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = _BLANK_RE.sub("\n\n", text)
    return text.strip()


def _cql_escape(value: str) -> str:
    """Escape a value for inclusion in a CQL string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


async def _api_get(path: str, *, params: dict | None = None) -> httpx.Response:
    async with httpx.AsyncClient(
        base_url=CONFLUENCE_BASE_URL,
        auth=(ATLASSIAN_EMAIL, ATLASSIAN_TOKEN),
        timeout=30.0,
        headers={"Accept": "application/json"},
    ) as client:
        resp = await client.get(path, params=params)
    if resp.status_code == 401:
        raise RuntimeError(
            "confluence rejected credentials (401); check ATLASSIAN_EMAIL "
            "and ATLASSIAN_TOKEN"
        )
    if resp.status_code == 403:
        raise RuntimeError(f"forbidden: {path} (your account lacks permission)")
    if resp.status_code == 404:
        raise RuntimeError(f"not found: {path}")
    if resp.status_code >= 400:
        raise RuntimeError(
            f"GET {path} failed (HTTP {resp.status_code}): {resp.text[:500]}"
        )
    return resp


@mcp.tool()
async def who_am_i() -> dict:
    """Return account summary (account_id, email, display_name) for the
    Confluence user the MCP is authenticated as. Use this as a sanity check."""
    resp = await _api_get("/rest/api/user/current")
    data = resp.json()
    return {
        "account_id": data.get("accountId"),
        "email": data.get("email"),
        "display_name": data.get("displayName"),
        "account_type": data.get("accountType"),
    }


@mcp.tool()
async def search_pages(
    query: str, space: str = "", limit: int = 10
) -> list[dict]:
    """Search Confluence pages by free-text query.

    `query` is matched against page text and title. `space` is an optional
    space key to narrow the search (e.g. 'FLOW'). `limit` is capped at 50,
    default 10. Results are ordered by last-modified (newest first).

    Each result is `{id, title, space, url, last_modified}`. Feed `id` into
    `read_page(page_id)` to get the body.
    """
    query = query.strip()
    if not query:
        raise ValueError("query must be non-empty")
    if len(query) > MAX_QUERY_LEN:
        raise ValueError(f"query too long: max {MAX_QUERY_LEN} chars")
    if space and not SPACE_KEY_RE.match(space):
        raise ValueError(
            f"invalid space {space!r}: letters, digits, underscore only"
        )
    if not (1 <= limit <= MAX_LIMIT):
        raise ValueError(f"invalid limit {limit!r}: 1..{MAX_LIMIT}")

    cql_parts = ['type = "page"', f'text ~ "{_cql_escape(query)}"']
    if space:
        cql_parts.append(f'space = "{space}"')
    cql = " AND ".join(cql_parts) + " ORDER BY lastModified DESC"

    resp = await _api_get(
        "/rest/api/content/search",
        params={"cql": cql, "limit": limit, "expand": "space,version"},
    )
    results = resp.json().get("results", []) or []

    site_base = CONFLUENCE_BASE_URL
    out: list[dict] = []
    for r in results:
        webui = (r.get("_links") or {}).get("webui") or ""
        out.append(
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "space": (r.get("space") or {}).get("key"),
                "url": f"{site_base}{webui}" if webui else None,
                "last_modified": (r.get("version") or {}).get("when"),
            }
        )
    return out


@mcp.tool()
async def read_page(page_id: str, format: str = "text") -> dict:
    """Read a single Confluence page by ID.

    `page_id` is the numeric ID from a page URL (.../pages/<id>/<title>) or
    from `search_pages()`. `format` controls the body representation:
      - 'text'    (default) rendered HTML stripped to plain text
      - 'storage' raw Confluence storage XHTML (good for round-tripping)
      - 'view'    rendered HTML (with macros expanded)

    Returns `{id, title, space, version, url, last_modified, format, body}`.
    """
    if not PAGE_ID_RE.match(page_id):
        raise ValueError(f"invalid page_id {page_id!r}: digits only")
    if format not in VALID_FORMATS:
        raise ValueError(
            f"invalid format {format!r}: one of {sorted(VALID_FORMATS)}"
        )

    expand = "space,version,body.storage" if format == "storage" else "space,version,body.view"
    resp = await _api_get(
        f"/rest/api/content/{page_id}", params={"expand": expand}
    )
    data = resp.json()
    body = (data.get("body") or {})
    if format == "storage":
        raw = (body.get("storage") or {}).get("value") or ""
        rendered = raw
    else:
        raw = (body.get("view") or {}).get("value") or ""
        rendered = _strip_html(raw) if format == "text" else raw

    webui = (data.get("_links") or {}).get("webui") or ""
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "space": (data.get("space") or {}).get("key"),
        "version": (data.get("version") or {}).get("number"),
        "last_modified": (data.get("version") or {}).get("when"),
        "url": f"{CONFLUENCE_BASE_URL}{webui}" if webui else None,
        "format": format,
        "body": rendered,
    }


def main() -> None:
    run(mcp)
