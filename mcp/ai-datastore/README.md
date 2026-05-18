# ai-datastore

Agent-facing datastore MCP for workflow notes.

- Stores note files under `/Users/aethier/playground/ai_datastore/<workflow_id>/`.
- Stores note/label metadata in CSV files under
  `/Users/aethier/playground/ai_datastore/` via `csvq`.
- Exposes tools for:
  - `upsert_note(...)` (create/update) from inline content or a source file path
  - `get_note(...)` by `workflow_id` + `note_id` (returns metadata + content)
  - `delete_note(...)`
  - `delete_label(...)` with immediate garbage collection of unlabeled notes
  - `get_labels(workspace_id=None)` for unique labels (scoped or global)
  - `search_notes(...)` using nested boolean label DSL

This MCP uses the host bridge for file and CSV-backed metadata operations so data lives on
the host filesystem.

`upsert_note` requires a short descriptive `name`. The server cleanses it
(removes unsupported characters, normalizes whitespace, enforces max length),
then filenames are generated as `<note_id>--<slug(name)>.md`.
Optionally pass `filename_hint` to append a suffix:
`<note_id>--<slug(name)>--<slug(filename_hint)>.md`.

## Run

```bash
./bin/bridge.sh start
./bin/manager start ai-datastore
```

## search_notes DSL

`search_notes` accepts a JSON `query` object with nested operators:

- `{"label":"critical"}`
- `{"and":[{"label":"backend"},{"label":"urgent"}]}`
- `{"or":[{"label":"backend"},{"not":{"label":"deprecated"}}]}`
- `{"in":["critical","urgent"]}` (`in` is sugar lowered to OR)

Example call:

```bash
./bin/mcp ai-datastore call search_notes \
  query='{"and":[{"label":"backend"},{"not":{"in":["wip","blocked"]}}]}'
```

Return shape:

```json
{
  "matches": [
    {"workflow_id": "FLOW-1234", "note_id": "deploy-plan", "labels": ["backend", "release"]},
    {"workflow_id": "FLOW-1234", "note_id": "rollback-checklist", "labels": ["backend", "ops"]}
  ]
}
```
