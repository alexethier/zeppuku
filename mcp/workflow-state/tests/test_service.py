from __future__ import annotations

import unittest

from aethier_mcp_workflow_state.service import WorkflowStateService


class _FakeRepo:
    def __init__(self) -> None:
        self.rows: dict[str, str] = {}
        self.ensure_calls = 0

    async def ensure_schema(self) -> None:
        self.ensure_calls += 1

    async def create(self, workflow_id: str, initial_state: str) -> None:
        if workflow_id in self.rows:
            raise ValueError(f"workflow already exists: {workflow_id}")
        self.rows[workflow_id] = initial_state

    async def get_state(self, workflow_id: str) -> str | None:
        return self.rows.get(workflow_id)

    async def list_workflows(self) -> list[dict[str, str]]:
        return [
            {"workflow_id": workflow_id, "state": state}
            for workflow_id, state in sorted(self.rows.items())
        ]

    async def transition(self, workflow_id: str, to_state: str) -> None:
        if workflow_id not in self.rows:
            raise ValueError(f"workflow not found: {workflow_id}")
        self.rows[workflow_id] = to_state

    async def delete(self, workflow_id: str) -> None:
        if workflow_id not in self.rows:
            raise ValueError(f"workflow not found: {workflow_id}")
        del self.rows[workflow_id]


class WorkflowStateServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_get_workflow(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())

        created = await service.create_workflow("FLOW-101", "backlog")
        fetched = await service.get_workflow("FLOW-101")

        self.assertIsNone(created)
        self.assertEqual(fetched, "backlog")

    async def test_transition_updates_state(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow("FLOW-102", "implementation_plan:drafted")

        transitioned = await service.transition("FLOW-102", "implementation_plan:accepted")
        fetched = await service.get_workflow("FLOW-102")

        self.assertIsNone(transitioned)
        self.assertEqual(fetched, "implementation_plan:accepted")

    async def test_transition_rejects_invalid_edge(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow("FLOW-103", "backlog")

        with self.assertRaises(ValueError):
            await service.transition("FLOW-103", "implemented")

        fetched = await service.get_workflow("FLOW-103")
        self.assertEqual(fetched, "backlog")

    async def test_denied_state_loops_back_to_previous_step(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow("FLOW-104", "implementation_plan:drafted")
        await service.transition("FLOW-104", "implementation_plan:denied")

        await service.transition("FLOW-104", "implementation_plan:drafted")
        fetched = await service.get_workflow("FLOW-104")
        self.assertEqual(fetched, "implementation_plan:drafted")

    async def test_in_depth_denied_loops_back_to_implemented(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow("FLOW-104A", "implementation:accepted")
        await service.transition("FLOW-104A", "in_depth_review:denied")
        await service.transition("FLOW-104A", "implemented")

        fetched = await service.get_workflow("FLOW-104A")
        self.assertEqual(fetched, "implemented")

    async def test_repeated_test_moves_into_jenkins_states(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow("FLOW-104B", "tested:instrumentation")
        await service.transition(
            "FLOW-104B",
            "tested:instrumentation:repeated:denied",
        )
        await service.transition("FLOW-104B", "jenkins_build:failure")

        fetched = await service.get_workflow("FLOW-104B")
        self.assertEqual(fetched, "jenkins_build:failure")

    async def test_final_jenkins_success_ready_state_is_terminal(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow(
            "FLOW-105",
            "final_jenkins_build:success:ready_for_human",
        )

        with self.assertRaises(ValueError):
            await service.transition("FLOW-105", "backlog")

    async def test_smoke_test_plan_accepted_requires_instrumentation_state(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow("FLOW-105A", "smoke_test_plan:accepted")

        await service.transition("FLOW-105A", "instrumentation_added")
        await service.transition("FLOW-105A", "test_plan_with_instrumentation_added")
        await service.transition("FLOW-105A", "tested:instrumentation")

        fetched = await service.get_workflow("FLOW-105A")
        self.assertEqual(fetched, "tested:instrumentation")

    async def test_jenkins_success_requires_cleanup_then_final_states(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow("FLOW-105B", "jenkins_build:success")

        await service.transition("FLOW-105B", "cleanup:remove_instrumentation")
        await service.transition("FLOW-105B", "final_smoke_test:accepted")
        await service.transition(
            "FLOW-105B",
            "final_jenkins_build:success:ready_for_human",
        )

        fetched = await service.get_workflow("FLOW-105B")
        self.assertEqual(fetched, "final_jenkins_build:success:ready_for_human")

    async def test_get_missing_workflow_raises(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        with self.assertRaises(ValueError):
            await service.get_workflow("FLOW-999")

    async def test_list_workflows_returns_all_rows(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow("FLOW-107", "backlog")
        await service.create_workflow("FLOW-108", "implemented")

        rows = await service.list_workflows()

        self.assertEqual(
            rows,
            [
                {"workflow_id": "FLOW-107", "state": "backlog"},
                {"workflow_id": "FLOW-108", "state": "implemented"},
            ],
        )

    async def test_delete_workflow_removes_row(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        await service.create_workflow("FLOW-109", "backlog")

        deleted = await service.delete_workflow("FLOW-109")
        rows = await service.list_workflows()

        self.assertIsNone(deleted)
        self.assertEqual(rows, [])

    async def test_create_rejects_unknown_state(self) -> None:
        service = WorkflowStateService(repo=_FakeRepo())
        with self.assertRaises(ValueError):
            await service.create_workflow("FLOW-106", "planning")


if __name__ == "__main__":
    unittest.main()
