"""csvq-backed access helpers executed on the host via the bridge."""
from __future__ import annotations

from csvq_adapter import CsvqHostAdapter, sql_literal as _sql_literal

DATASTORE_ROOT = "/Users/aethier/playground/ai_datastore"
LOCK_PATH = f"{DATASTORE_ROOT}/datastore.lock"

NOTES_TABLE = "notes"
NOTES_CSV = f"{DATASTORE_ROOT}/{NOTES_TABLE}.csv"
NOTES_HEADERS = [
    "workflow_id",
    "note_id",
    "note_description",
    "rel_path",
    "created_at",
    "updated_at",
]

NOTE_LABELS_TABLE = "note_labels"
NOTE_LABELS_CSV = f"{DATASTORE_ROOT}/{NOTE_LABELS_TABLE}.csv"
NOTE_LABELS_HEADERS = ["workflow_id", "note_id", "label"]

_adapter = CsvqHostAdapter(root=DATASTORE_ROOT, lock_path=LOCK_PATH)


async def ensure_schema() -> None:
    await _adapter.ensure_csv_schema(csv_path=NOTES_CSV, expected_headers=NOTES_HEADERS)
    await _adapter.ensure_csv_schema(
        csv_path=NOTE_LABELS_CSV,
        expected_headers=NOTE_LABELS_HEADERS,
    )


async def query(sql: str) -> list[dict]:
    return await _adapter.execute(sql)


def sql_literal(value: str) -> str:
    return _sql_literal(value)
