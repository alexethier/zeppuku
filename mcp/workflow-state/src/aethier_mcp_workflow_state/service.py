"""Workflow state machine service layer."""
from __future__ import annotations

from .repository import WorkflowRepository
from .validators import validate_state, validate_transition, validate_workflow_id


class WorkflowStateService:
    """State-agnostic workflow operations over a csvq-backed snapshot table."""

    def __init__(self, repo: WorkflowRepository | None = None) -> None:
        self._repo = repo or WorkflowRepository()

    async def _ensure_ready(self) -> None:
        await self._repo.ensure_schema()

    async def create_workflow(self, workflow_id: str, initial_state: str) -> None:
        workflow_id = validate_workflow_id(workflow_id)
        initial_state = validate_state(initial_state)
        await self._ensure_ready()

        await self._repo.create(workflow_id=workflow_id, initial_state=initial_state)

    async def get_workflow(self, workflow_id: str) -> str:
        workflow_id = validate_workflow_id(workflow_id)
        await self._ensure_ready()

        state = await self._repo.get_state(workflow_id)
        if state is None:
            raise ValueError(f"workflow not found: {workflow_id}")
        return state

    async def list_workflows(self) -> list[dict[str, str]]:
        await self._ensure_ready()
        return await self._repo.list_workflows()

    async def transition(self, workflow_id: str, to_state: str) -> None:
        workflow_id = validate_workflow_id(workflow_id)
        await self._ensure_ready()

        current_state = await self._repo.get_state(workflow_id)
        if current_state is None:
            raise ValueError(f"workflow not found: {workflow_id}")
        to_state = validate_state(to_state)
        validate_transition(current_state=current_state, to_state=to_state)

        await self._repo.transition(workflow_id=workflow_id, to_state=to_state)

    async def delete_workflow(self, workflow_id: str) -> None:
        workflow_id = validate_workflow_id(workflow_id)
        await self._ensure_ready()
        await self._repo.delete(workflow_id=workflow_id)
