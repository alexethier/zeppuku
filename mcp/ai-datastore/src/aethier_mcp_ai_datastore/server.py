"""ai-datastore MCP server: workflow notes + labels with CSV metadata."""
from __future__ import annotations

from aethier_mcp_core import create_server, run

from .service import DatastoreService

mcp = create_server("ai-datastore")
svc = DatastoreService()


@mcp.tool()
async def upsert_note(
    workflow_id: str,
    note_description: str,
    labels: list[str],
    name: str,
    filename_hint: str | None = None,
    note_id: str | None = None,
    content: str | None = None,
    file_path: str | None = None,
) -> dict:
    """Create or update a note.

    Exactly one content source is required:
    - `content`: inline note text
    - `file_path`: host file path to read
    `note_id` is optional. If omitted, a workflow-scoped incremental ID is assigned.
    Required `name` is a short descriptive title used in the filename.
    Optional `filename_hint` appends a suffix hint in the filename.
    """
    return await svc.upsert_note(
        workflow_id=workflow_id,
        note_description=note_description,
        labels=labels,
        name=name,
        filename_hint=filename_hint,
        note_id=note_id,
        content=content,
        file_path=file_path,
    )


@mcp.tool()
async def get_note(workflow_id: str, note_id: str) -> dict:
    """Get one note by workflow_id + note_id, including note content."""
    return await svc.get_note(workflow_id=workflow_id, note_id=note_id)


@mcp.tool()
async def delete_note(workflow_id: str, note_id: str) -> dict:
    """Delete a note's file and metadata by workflow_id + note_id."""
    return await svc.delete_note(workflow_id=workflow_id, note_id=note_id)


@mcp.tool()
async def delete_label(label: str) -> dict:
    """Delete a label."""
    return await svc.delete_label(label)


@mcp.tool()
async def get_labels(workspace_id: str | None = None) -> dict:
    """Return distinct labels.

    - If workspace_id is provided, returns labels only for that workflow scope.
    - If workspace_id is omitted, returns all labels in the datastore.
    """
    return await svc.get_labels(workspace_id=workspace_id)


@mcp.tool()
async def search_notes_by_label(
    query: dict,
    workflow_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Search notes by label DSL. Call usage('search_notes_by_label')."""
    return await svc.search_notes_by_label(
        query=query,
        workflow_id=workflow_id,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
async def search_notes_by_workflow_id(
    workflow_id: str,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """List all notes in one workflow. Call usage('search_notes_by_workflow_id')."""
    return await svc.search_notes_by_workflow_id(
        workflow_id=workflow_id,
        limit=limit,
        offset=offset,
    )


def main() -> None:
    run(mcp)
