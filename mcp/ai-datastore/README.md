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
  - `search_notes_by_label(...)` using nested boolean label DSL (optional workflow scope)
  - `search_notes_by_workflow_id(...)` for full listing in one workflow

This MCP uses the host bridge for file and CSV-backed metadata operations so data lives on
the host filesystem.

`upsert_note` requires a short descriptive `name`. The server cleanses it
(removes unsupported characters, normalizes whitespace, enforces max length),
then filenames are generated as `<note_id>--<slug(name)>.md`.
Optionally pass `filename_hint` to append a suffix:
`<note_id>--<slug(name)>--<slug(filename_hint)>.md`.

On every `upsert_note`, the datastore also injects canonical UTC system labels:
- `create_date_utc:YYYY-MM-DD` (preserved from original creation date)
- `updated_date_utc:YYYY-MM-DDtHH:MM:SSz` (refreshed on every update)

## Run

```bash
./bin/bridge.sh start
./bin/manager start ai-datastore
```

## search_notes_by_label DSL

`search_notes_by_label` accepts a JSON `query` object with nested operators
and optional `workflow_id`:

- `{}`
- `{"label":"critical"}`
- `{"and":[{"label":"backend"},{"label":"urgent"}]}`
- `{"or":[{"label":"backend"},{"not":{"label":"deprecated"}}]}`
- `{"in":["critical","urgent"]}` (`in` is sugar lowered to OR)

Example call:

```bash
./bin/mcp ai-datastore call search_notes_by_label \
  workflow_id='FLOW-1234' \
  query='{"and":[{"label":"backend"},{"not":{"in":["wip","blocked"]}}]}'
```

## search_notes_by_workflow_id

List all notes in one workflow (same output shape as label search):

```bash
./bin/mcp ai-datastore call search_notes_by_workflow_id \
  workflow_id='FLOW-1234'
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
