# confluence

Read-only MCP for an Atlassian Confluence Cloud site. Talks directly to
the REST API via `httpx` with Basic auth (email + API token from
[id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens);
same creds as the `jira` MCP). Three tools: `who_am_i()` for auth
sanity; `search_pages(query, space="", limit=10)` running CQL
(`type = "page" AND text ~ "<query>" [AND space = "<space>"] ORDER BY
lastModified DESC`, capped 50) returning `{id, title, space, url,
last_modified}` per hit; and `read_page(page_id, format="text")` —
`"text"` strips HTML for LLMs, `"storage"` returns raw Confluence
XHTML, `"view"` returns rendered HTML. `page_id` validated as digits,
`space` as `[A-Za-z0-9_]+`, query strings escaped before CQL
interpolation. Required env: `CONFLUENCE_BASE_URL` (must include
`/wiki`, no trailing slash), `ATLASSIAN_EMAIL`, `ATLASSIAN_TOKEN`.
Container talks to Confluence directly over HTTPS — no host bridge
needed.

```bash
export CONFLUENCE_BASE_URL="https://example.atlassian.net/wiki"
export ATLASSIAN_EMAIL="you@example.com"
read -rs ATLASSIAN_TOKEN && export ATLASSIAN_TOKEN
./bin/manager start confluence
```
