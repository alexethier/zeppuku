# jira

Read-only MCP for an Atlassian Jira Cloud site. Talks directly to the
REST API v3 via `httpx` with Basic auth (email + API token from
[id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens);
same creds as the `confluence` MCP). Four tools: `who_am_i()` for auth
sanity; `list_projects(limit=50)` to discover project keys (e.g. FLOW,
SNOW); `search_issues(jql="", project="", limit=10)` against the new
`/search/jql` endpoint — empty `jql` becomes recent issues in `project`
(default `JIRA_DEFAULT_PROJECT`, falls back to `FLOW`), and unbounded
JQL gets `project = "<project>" AND` prepended automatically because
Atlassian rejects unbounded queries with HTTP 400; and `read_issue(key,
format="text")` returning summary/status/priority/assignee/dates/url
plus all comments (`format="text"` strips HTML for LLMs, `"html"`
returns rendered). Keys validated against `^[A-Z][A-Z0-9_]+-\d+$`.
Required env: `JIRA_BASE_URL` (no `/wiki`, no trailing slash),
`ATLASSIAN_EMAIL`, `ATLASSIAN_TOKEN`; optional `JIRA_DEFAULT_PROJECT`
(defaults `FLOW`). Container talks to Jira directly over HTTPS — no
host bridge needed.

```bash
export JIRA_BASE_URL="https://example.atlassian.net"
export ATLASSIAN_EMAIL="you@example.com"
read -rs ATLASSIAN_TOKEN && export ATLASSIAN_TOKEN
./bin/manager start jira
```
