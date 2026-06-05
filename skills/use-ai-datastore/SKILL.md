---
name: use-ai-datastore
description: Use when the user asks to offload a coding task (jira task) context as a note (implementation plans, test plans, review notes, test logs, proof artifacts), or load notes/context on a task.
---

# Use ai-datastore

Use the `ai-datastore` MCP to manage workflow notes under a `workflow_id`.

## Primary purpose

Use `ai-datastore` as a long-lived context store for complex Jira feature work.
It is the place to persist structured ticket knowledge so agents can resume work
without losing important details between sessions.

Typical artifacts to store per `workflow_id`:

- Implementation plans
- Test plans
- Code review notes
- Test execution notes
- Test logs
- Proof artifacts / verification evidence

Treat notes as durable ticket memory, not ad-hoc scratch text.

## When to use this

Use this skill when the user asks to:

- Offload or persist Jira ticket context for later reuse
- Save or update a workflow note
- Attach or update labels on a note
- Delete a note
- Delete a label globally from all notes
- Find note IDs by label logic (including nested boolean conditions)

## Ticket-oriented conventions

`create_note` can assign workflow-scoped incremental `note_id` values (`1`, `2`, ...)
when `note_id` is omitted.
`name` is required and should be short + descriptive; the server will cleanse
invalid characters and normalize it before filename generation.
Recommended names:

- `implementation-plan`
- `test-plan`
- `code-review-notes`
- `test-notes`
- `test-logs`
- `proof`

Recommended labels:

- `plan`
- `implementation`
- `test`
- `review`
- `logs`
- `proof`
- `status:wip`, `status:done`

To update a note over time, edit the file directly at the returned `abs_path`.

## Tool selection

- `create_note`: create a note and its labels
- `get_note`: read one note by `workflow_id` + `note_id` (returns metadata + paths + labels)
- `delete_note`: remove one note by `workflow_id` + `note_id`
- `delete_label`: remove a label globally and garbage-collect unlabeled notes
- `get_labels`: return unique labels globally or scoped to one workflow (`workspace_id`)
- `search_notes_by_label`: return matching note identifiers with labels (`workflow_id`, `note_id`, `labels`)

## Input contracts

### `create_note`

Required:

- `workflow_id`
- `note_description`
- `labels`
- `name` (short descriptive title; server-cleansed and slugged for filename)
- optional `filename_hint` (extra filename suffix hint; also cleansed + slugged)
- optional `note_id` (omit to create with system-assigned workflow-scoped incremental ID)

## Search DSL

`search_notes_by_label` uses a JSON AST in `query`.

Supported operators:

- `{"label":"foo"}`
- `{"and":[<expr>, <expr>, ...]}`
- `{"or":[<expr>, <expr>, ...]}`
- `{"not":<expr>}`
- `{"in":["foo","bar",...]}` (sugar lowered to OR)

Return shape:

- `{"matches":[{"workflow_id":"...","note_id":"...","labels":["..."]}, ...]}`

`search_notes_by_label` does not return note content. It returns IDs and labels only.

## Call patterns

### Create a note record

Call `create_note` with metadata fields. Then edit the created note file directly using
the returned `abs_path`.

### Delete one note

Call `delete_note(workflow_id, note_id)`.

### Read one note

Call `get_note(workflow_id, note_id)` to load metadata/paths. Then read the note file
directly from `abs_path` if the user asks for content.

### Delete a label globally

Call `delete_label(label)`.

This affects all workflows and may delete notes that become unlabeled.

### List available labels

Call `get_labels` with:

- optional `workspace_id` to scope results to one workflow
- omit `workspace_id` to list all labels in the datastore

### Search by nested logic

Call `search_notes_by_label` with:

- `query`: JSON AST
- optional `workflow_id`
- optional `limit` and `offset`

For more examples, see [examples.md](examples.md).

## Safety and behavior notes

- Prefer asking the user before destructive global label deletes unless explicitly requested.
- If the user asks to "find notes", default to `search_notes_by_label` first and return IDs.
- If the user asks for note content, run `search_notes_by_label` to find IDs when needed, then call `get_note` with the chosen `workflow_id` + `note_id`, then read content directly from the returned `abs_path`.
