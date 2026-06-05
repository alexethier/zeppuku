"""ai-datastore MCP server: workflow notes + labels with CSV metadata."""
from __future__ import annotations

from aethier_mcp_core import create_server, run

from .service import DatastoreService

mcp = create_server("ai-datastore")
svc = DatastoreService()


@mcp.tool()
async def create_note(
    workflow_id: str,
    note_description: str,
    labels: list[str],
    name: str,
    filename_hint: str | None = None,
    note_id: str | None = None,
    content: str | None = None,
    file_path: str | None = None,
) -> dict:
    """Create a note. Call usage('create_note') for details."""
    return await svc.create_note(
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
    """Get a note. Call usage('get_note') for details."""
    return await svc.get_note(workflow_id=workflow_id, note_id=note_id)


@mcp.tool()
async def delete_note(workflow_id: str, note_id: str) -> dict:
    """Delete one note. Call usage('delete_note') for details."""
    return await svc.delete_note(workflow_id=workflow_id, note_id=note_id)


@mcp.tool()
async def delete_label(label: str) -> dict:
    """Delete a label. Call usage('delete_label') for details."""
    return await svc.delete_label(label)


@mcp.tool()
async def get_labels(workspace_id: str | None = None) -> dict:
    """Get all labels in a workspace or globally. Call usage('get_labels') for details."""
    return await svc.get_labels(workspace_id=workspace_id)


@mcp.tool()
async def search_notes_by_label(
    query: dict,
    workflow_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Search notes by labels. Call usage('search_notes_by_label') for details."""
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
    """List workflow notes. Call usage('search_notes_by_workflow_id') for details."""
    return await svc.search_notes_by_workflow_id(
        workflow_id=workflow_id,
        limit=limit,
        offset=offset,
    )


def main() -> None:
    run(mcp)
