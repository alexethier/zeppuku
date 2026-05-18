# ai-datastore Examples

## upsert_note create from inline content (system note_id)

Use:

```json
{
  "workflow_id": "FLOW-1234",
  "note_description": "Deployment plan for staging",
  "name": "deployment-plan",
  "filename_hint": "v1",
  "labels": ["backend", "release"],
  "content": "Step 1: ...",
  "file_path": null
}
```

## upsert_note create from file_path (system note_id)

Use:

```json
{
  "workflow_id": "FLOW-1234",
  "note_description": "Imported incident summary",
  "name": "incident-summary",
  "labels": ["incident", "postmortem"],
  "content": null,
  "file_path": "/Users/aethier/playground/notes/incident.txt"
}
```

## upsert_note update for known note_id

```json
{
  "workflow_id": "FLOW-1234",
  "note_id": "1",
  "note_description": "Implementation plan v2",
  "name": "implementation-plan",
  "labels": ["plan", "implementation"],
  "content": "Updated plan..."
}
```

## get_note

```json
{
  "workflow_id": "FLOW-1234",
  "note_id": "1"
}
```

## delete_note

```json
{
  "workflow_id": "FLOW-1234",
  "note_id": "1"
}
```

## delete_label (global)

```json
{
  "label": "wip"
}
```

## get_labels (global and scoped)

```json
{
  "workspace_id": null
}
```

```json
{
  "workspace_id": "FLOW-1234"
}
```

## search_notes DSL examples

### Single label

```json
{
  "query": {"label": "backend"}
}
```

### In sugar

```json
{
  "query": {"in": ["critical", "urgent"]}
}
```

### Nested and/not

```json
{
  "query": {
    "and": [
      {"label": "backend"},
      {"not": {"or": [{"label": "wip"}, {"label": "blocked"}]}}
    ]
  }
}
```

### Scoped by workflow and path glob

```json
{
  "query": {"or": [{"label": "backend"}, {"label": "frontend"}]},
  "workflow_id": "FLOW-1234",
  "glob": "**/backend-*.md",
  "limit": 200,
  "offset": 0
}
```
