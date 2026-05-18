from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from csvq_adapter import CsvqHostAdapter


class CsvqHostAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_execute_forwards_query(self) -> None:
        adapter = CsvqHostAdapter(root="/tmp/data", lock_path="/tmp/data/lock")
        with patch.object(adapter, "_host_call", new_callable=AsyncMock) as mocked:
            mocked.return_value = {"rows": []}
            await adapter.execute("UPDATE tasks SET state = 'planned'")
            mocked.assert_awaited_once_with(
                "execute",
                {"query": "UPDATE tasks SET state = 'planned'"},
            )

    async def test_execute_returns_rows(self) -> None:
        adapter = CsvqHostAdapter(root="/tmp/data", lock_path="/tmp/data/lock")
        with patch.object(adapter, "_host_call", new_callable=AsyncMock) as mocked:
            mocked.return_value = {"rows": [{"workflow_id": "FLOW-1", "state": "planned"}]}
            rows = await adapter.execute("SELECT workflow_id, state FROM workflow_instances")
            self.assertEqual(rows[0]["state"], "planned")


if __name__ == "__main__":
    unittest.main()
