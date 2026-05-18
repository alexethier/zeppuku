"""workflow-state MCP server: minimal workflow state transitions over csvq."""
from __future__ import annotations

from aethier_mcp_core import create_server, run

from .service import WorkflowStateService

mcp = create_server("workflow-state")
svc = WorkflowStateService()


@mcp.tool()
async def create_workflow(workflow_id: str, initial_state: str) -> None:
    """Create a new workflow record. Call usage('create_workflow') for details."""
    await svc.create_workflow(
        workflow_id=workflow_id,
        initial_state=initial_state,
    )


@mcp.tool()
async def get_workflow(workflow_id: str) -> str:
    """Fetch current workflow state. Call usage('get_workflow') for details."""
    return await svc.get_workflow(workflow_id=workflow_id)


@mcp.tool()
async def list_workflows() -> list[dict[str, str]]:
    """List all workflows and their states. Call usage('list_workflows') for details."""
    return await svc.list_workflows()


@mcp.tool()
async def transition_workflow(workflow_id: str, to_state: str) -> None:
    """Update workflow state. Call usage('transition_workflow') for details."""
    await svc.transition(workflow_id=workflow_id, to_state=to_state)


@mcp.tool()
async def delete_workflow(workflow_id: str) -> None:
    """Delete one workflow record. Call usage('delete_workflow') for details."""
    await svc.delete_workflow(workflow_id=workflow_id)


def main() -> None:
    run(mcp)
