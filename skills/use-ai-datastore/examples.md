# ai-datastore Examples

## create_note with system note_id

Use:

```json
{
  "workflow_id": "FLOW-1234",
  "note_description": "Deployment plan for staging",
  "name": "deployment-plan",
  "filename_hint": "v1",
  "labels": ["backend", "release"]
}
```

## create_note with caller-provided note_id

```json
{
  "workflow_id": "FLOW-1234",
  "note_id": "1",
  "note_description": "Implementation plan",
  "name": "implementation-plan",
  "labels": ["plan", "implementation"]
}
```

After creating the note, write content directly to the returned `abs_path`.

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

## search_notes_by_label DSL examples

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

### Scoped by workflow

```json
{
  "query": {"or": [{"label": "backend"}, {"label": "frontend"}]},
  "workflow_id": "FLOW-1234",
  "limit": 200,
  "offset": 0
}
```
