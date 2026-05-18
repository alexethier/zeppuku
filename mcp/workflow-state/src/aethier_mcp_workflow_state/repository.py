"""Workflow-specific repository built on the generic csvq adapter."""
from __future__ import annotations

from csvq_adapter import CsvqHostAdapter, sql_literal

DATASTORE_ROOT = "/Users/aethier/playground/workflow_state"
TABLE_NAME = "workflow_instances"
CSV_PATH = f"{DATASTORE_ROOT}/{TABLE_NAME}.csv"
LOCK_PATH = f"{DATASTORE_ROOT}/workflow.lock"
EXPECTED_HEADERS = ["workflow_id", "state"]


class WorkflowRepository:
    """Persistence operations for the workflow snapshot file."""

    def __init__(self, adapter: CsvqHostAdapter | None = None) -> None:
        self._adapter = adapter or CsvqHostAdapter(
            root=DATASTORE_ROOT,
            lock_path=LOCK_PATH,
        )

    async def ensure_schema(self) -> None:
        await self._adapter.ensure_csv_schema(
            csv_path=CSV_PATH,
            expected_headers=EXPECTED_HEADERS,
        )

    async def get_state(self, workflow_id: str) -> str | None:
        rows = await self._adapter.execute(
            "SELECT workflow_id, state "
            f"FROM {TABLE_NAME} "
            f"WHERE workflow_id = {sql_literal(workflow_id)}"
        )
        row = rows[0] if rows else None
        if row is None:
            return None
        return str(row["state"])

    async def create(self, workflow_id: str, initial_state: str) -> None:
        existing = await self.get_state(workflow_id)
        if existing is not None:
            raise ValueError(f"workflow already exists: {workflow_id}")

        await self._adapter.execute(
            f"INSERT INTO {TABLE_NAME} (workflow_id, state) "
            f"VALUES ({sql_literal(workflow_id)}, {sql_literal(initial_state)})"
        )
        created = await self.get_state(workflow_id)
        if created is None:
            raise RuntimeError("create did not persist row")

    async def list_workflows(self) -> list[dict[str, str]]:
        rows = await self._adapter.execute(
            "SELECT workflow_id, state "
            f"FROM {TABLE_NAME} "
            "ORDER BY workflow_id"
        )
        return [
            {
                "workflow_id": str(row["workflow_id"]),
                "state": str(row["state"]),
            }
            for row in rows
        ]

    async def transition(self, workflow_id: str, to_state: str) -> None:
        existing = await self.get_state(workflow_id)
        if existing is None:
            raise ValueError(f"workflow not found: {workflow_id}")

        await self._adapter.execute(
            f"UPDATE {TABLE_NAME} "
            f"SET state = {sql_literal(to_state)} "
            f"WHERE workflow_id = {sql_literal(workflow_id)}"
        )
        updated = await self.get_state(workflow_id)
        if updated is None:
            raise RuntimeError("transition lost row unexpectedly")

    async def delete(self, workflow_id: str) -> None:
        existing = await self.get_state(workflow_id)
        if existing is None:
            raise ValueError(f"workflow not found: {workflow_id}")

        await self._adapter.execute(
            f"DELETE FROM {TABLE_NAME} "
            f"WHERE workflow_id = {sql_literal(workflow_id)}"
        )
        deleted = await self.get_state(workflow_id)
        if deleted is not None:
            raise RuntimeError("delete did not remove row")
