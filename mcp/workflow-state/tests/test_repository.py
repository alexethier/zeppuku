from __future__ import annotations

import unittest

from aethier_mcp_workflow_state.repository import WorkflowRepository


class _FakeAdapter:
    def __init__(self) -> None:
        self.rows: dict[str, str] = {}
        self.ensure_calls = 0
        self.executed_queries: list[str] = []

    async def ensure_csv_schema(self, *, csv_path: str, expected_headers: list[str]) -> None:
        self.ensure_calls += 1
        self.csv_path = csv_path
        self.expected_headers = expected_headers

    async def execute(self, query: str) -> list[dict]:
        self.executed_queries.append(query)
        statement = query.lower()
        if statement.startswith("select "):
            if "where workflow_id =" not in statement:
                return [
                    {"workflow_id": workflow_id, "state": state}
                    for workflow_id, state in sorted(self.rows.items())
                ]
            for workflow_id, state in self.rows.items():
                if f"'{workflow_id.lower()}'" in statement:
                    return [{"workflow_id": workflow_id, "state": state}]
            return []
        if "insert into workflow_instances" in statement:
            left = query.split("VALUES (", 1)[1]
            workflow_id = left.split(",", 1)[0].strip().strip("'")
            state = left.split(",", 1)[1].split(")", 1)[0].strip().strip("'")
            self.rows[workflow_id] = state
            return []
        if "update workflow_instances" in statement:
            parts = query.split("SET state = ", 1)[1]
            state = parts.split(" WHERE ", 1)[0].strip().strip("'")
            workflow_id = query.split("workflow_id = ", 1)[1].strip().strip("'")
            if workflow_id not in self.rows:
                raise ValueError("workflow not found")
            self.rows[workflow_id] = state
            return []
        if "delete from workflow_instances" in statement:
            workflow_id = query.split("workflow_id = ", 1)[1].strip().strip("'")
            self.rows.pop(workflow_id, None)
            return []
        return []


class WorkflowRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_get_by_id(self) -> None:
        repo = WorkflowRepository(adapter=_FakeAdapter())
        await repo.ensure_schema()

        created = await repo.create("FLOW-111", "backlog")
        fetched = await repo.get_state("FLOW-111")

        self.assertIsNone(created)
        self.assertEqual(fetched, "backlog")

    async def test_transition_uses_lock(self) -> None:
        adapter = _FakeAdapter()
        repo = WorkflowRepository(adapter=adapter)
        await repo.create("FLOW-222", "implementation_plan:drafted")

        updated = await repo.transition("FLOW-222", "implementation_plan:accepted")
        fetched = await repo.get_state("FLOW-222")

        self.assertIsNone(updated)
        self.assertEqual(fetched, "implementation_plan:accepted")
        self.assertGreaterEqual(len(adapter.executed_queries), 1)

    async def test_create_duplicate_raises(self) -> None:
        repo = WorkflowRepository(adapter=_FakeAdapter())
        await repo.create("FLOW-333", "backlog")
        with self.assertRaises(ValueError):
            await repo.create("FLOW-333", "planning")

    async def test_list_workflows_returns_all_rows(self) -> None:
        repo = WorkflowRepository(adapter=_FakeAdapter())
        await repo.create("FLOW-400", "backlog")
        await repo.create("FLOW-401", "implemented")

        rows = await repo.list_workflows()

        self.assertEqual(
            rows,
            [
                {"workflow_id": "FLOW-400", "state": "backlog"},
                {"workflow_id": "FLOW-401", "state": "implemented"},
            ],
        )

    async def test_delete_removes_workflow(self) -> None:
        repo = WorkflowRepository(adapter=_FakeAdapter())
        await repo.create("FLOW-402", "backlog")

        deleted = await repo.delete("FLOW-402")
        fetched = await repo.get_state("FLOW-402")

        self.assertIsNone(deleted)
        self.assertIsNone(fetched)


if __name__ == "__main__":
    unittest.main()
