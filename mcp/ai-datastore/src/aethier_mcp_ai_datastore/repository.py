"""Repository layer for ai-datastore csvq metadata."""
from __future__ import annotations

from . import db
from .models import NoteRecord, SearchNoteMatch
from .search_dsl import LabelExpr, evaluate_expr, extract_labels


async def ensure_schema() -> None:
    await db.ensure_schema()


async def get_note_by_key(workflow_id: str, note_id: str) -> NoteRecord | None:
    rows = await db.query(
        "SELECT workflow_id, note_id, note_description, rel_path, created_at, updated_at "
        f"FROM {db.NOTES_TABLE} "
        f"WHERE workflow_id = {db.sql_literal(workflow_id)} "
        f"AND note_id = {db.sql_literal(note_id)}"
    )
    if not rows:
        return None
    return NoteRecord.from_row(rows[0])


async def list_labels_for_note(workflow_id: str, note_id: str) -> list[str]:
    rows = await db.query(
        "SELECT label "
        f"FROM {db.NOTE_LABELS_TABLE} "
        f"WHERE workflow_id = {db.sql_literal(workflow_id)} "
        f"AND note_id = {db.sql_literal(note_id)} "
        "ORDER BY label"
    )
    return [str(r["label"]) for r in rows]


async def list_unique_labels(workflow_id: str | None = None) -> list[str]:
    where = ""
    if workflow_id is not None:
        where = f"WHERE workflow_id = {db.sql_literal(workflow_id)}"
    rows = await db.query(
        "SELECT DISTINCT label "
        f"FROM {db.NOTE_LABELS_TABLE} "
        f"{where} "
        "ORDER BY label"
    )
    return [str(r["label"]) for r in rows]


async def list_note_ids_for_workflow(workflow_id: str) -> list[str]:
    rows = await db.query(
        "SELECT note_id "
        f"FROM {db.NOTES_TABLE} "
        f"WHERE workflow_id = {db.sql_literal(workflow_id)}"
    )
    return [str(r["note_id"]) for r in rows]


async def create_note_metadata(
    workflow_id: str,
    note_id: str,
    note_description: str,
    rel_path: str,
    labels: list[str],
    now_iso: str,
) -> tuple[NoteRecord, list[str]]:
    existing = await get_note_by_key(workflow_id, note_id)
    if existing is not None:
        raise ValueError(
            f"duplicate note key: workflow_id={workflow_id!r} note_id={note_id!r}"
        )

    await db.query(
        f"INSERT INTO {db.NOTES_TABLE} "
        "(workflow_id, note_id, note_description, rel_path, created_at, updated_at) "
        f"VALUES ({db.sql_literal(workflow_id)}, {db.sql_literal(note_id)}, "
        f"{db.sql_literal(note_description)}, {db.sql_literal(rel_path)}, "
        f"{db.sql_literal(now_iso)}, {db.sql_literal(now_iso)})"
    )

    await db.query(
        f"DELETE FROM {db.NOTE_LABELS_TABLE} "
        f"WHERE workflow_id = {db.sql_literal(workflow_id)} "
        f"AND note_id = {db.sql_literal(note_id)}"
    )
    for label in labels:
        await db.query(
            f"INSERT INTO {db.NOTE_LABELS_TABLE} (workflow_id, note_id, label) "
            f"VALUES ({db.sql_literal(workflow_id)}, {db.sql_literal(note_id)}, "
            f"{db.sql_literal(label)})"
        )

    record = await get_note_by_key(workflow_id, note_id)
    if record is None:
        raise RuntimeError("create_note_metadata failed to persist note")
    applied_labels = await list_labels_for_note(workflow_id, note_id)
    return record, applied_labels


async def delete_note_metadata(workflow_id: str, note_id: str) -> NoteRecord | None:
    existing = await get_note_by_key(workflow_id, note_id)
    if existing is None:
        return None
    await db.query(
        f"DELETE FROM {db.NOTE_LABELS_TABLE} "
        f"WHERE workflow_id = {db.sql_literal(workflow_id)} "
        f"AND note_id = {db.sql_literal(note_id)}"
    )
    await db.query(
        f"DELETE FROM {db.NOTES_TABLE} "
        f"WHERE workflow_id = {db.sql_literal(workflow_id)} "
        f"AND note_id = {db.sql_literal(note_id)}"
    )
    return existing


async def delete_label_and_collect_unlabeled(label: str) -> dict:
    linked_rows = await db.query(
        "SELECT workflow_id, note_id "
        f"FROM {db.NOTE_LABELS_TABLE} "
        f"WHERE label = {db.sql_literal(label)}"
    )
    if not linked_rows:
        return {
            "label_found": False,
            "detached_links": 0,
            "unlabeled_notes": [],
        }

    detached_links = len(linked_rows)
    await db.query(
        f"DELETE FROM {db.NOTE_LABELS_TABLE} "
        f"WHERE label = {db.sql_literal(label)}"
    )

    orphan_rows = await db.query(
        "SELECT workflow_id, note_id, note_description, rel_path, created_at, updated_at "
        f"FROM {db.NOTES_TABLE} n "
        "WHERE NOT EXISTS ("
        f"  SELECT 1 FROM {db.NOTE_LABELS_TABLE} nl "
        "  WHERE nl.workflow_id = n.workflow_id "
        "    AND nl.note_id = n.note_id"
        ")"
    )
    return {
        "label_found": True,
        "detached_links": detached_links,
        "unlabeled_notes": [NoteRecord.from_row(r) for r in orphan_rows],
    }


async def delete_notes_by_keys(note_keys: list[tuple[str, str]]) -> int:
    if not note_keys:
        return 0
    deleted = 0
    for workflow_id, note_id in note_keys:
        await db.query(
            f"DELETE FROM {db.NOTES_TABLE} "
            f"WHERE workflow_id = {db.sql_literal(workflow_id)} "
            f"AND note_id = {db.sql_literal(note_id)}"
        )
        deleted += 1
    return deleted


async def prune_unreferenced_labels() -> int:
    # no-op for csvq datastore because labels are represented by note_labels rows
    return 0


async def search_note_identifiers(
    workflow_id: str | None,
    *,
    expr: LabelExpr | None,
    limit: int,
    offset: int,
) -> list[SearchNoteMatch]:
    """Evaluate a normalized label expression and return note identifiers + labels."""
    where = ""
    if workflow_id is not None:
        where = f"WHERE workflow_id = {db.sql_literal(workflow_id)}"
    scope_rows = await db.query(
        f"""
        SELECT workflow_id, note_id, rel_path
        FROM {db.NOTES_TABLE}
        {where}
        ORDER BY workflow_id, note_id
        """,
    )
    if not scope_rows:
        return []

    universe_keys = {(str(r["workflow_id"]), str(r["note_id"])) for r in scope_rows}
    ordered_keys = [
        (str(r["workflow_id"]), str(r["note_id"]))
        for r in scope_rows
    ]
    row_by_key = {
        (str(r["workflow_id"]), str(r["note_id"])): r for r in scope_rows
    }

    if expr is None:
        matched_keys = universe_keys
    else:
        labels = sorted(extract_labels(expr))
        label_hits: dict[str, set[tuple[str, str]]] = {name: set() for name in labels}
        for label in labels:
            label_rows = await db.query(
                "SELECT workflow_id, note_id "
                f"FROM {db.NOTE_LABELS_TABLE} "
                f"WHERE label = {db.sql_literal(label)}"
            )
            for row in label_rows:
                key = (str(row["workflow_id"]), str(row["note_id"]))
                if key in universe_keys:
                    label_hits[label].add(key)

        matched_keys = evaluate_expr(expr, label_hits=label_hits, universe=universe_keys)
    ordered_match_keys = [key for key in ordered_keys if key in matched_keys]
    sliced_keys = ordered_match_keys[offset : offset + limit]
    if not sliced_keys:
        return []

    wanted_keys = set(sliced_keys)
    labels_where = ""
    if workflow_id is not None:
        labels_where = f"WHERE workflow_id = {db.sql_literal(workflow_id)}"
    label_rows = await db.query(
        f"""
        SELECT workflow_id, note_id, label
        FROM {db.NOTE_LABELS_TABLE}
        {labels_where}
        """
    )
    labels_by_key: dict[tuple[str, str], list[str]] = {key: [] for key in sliced_keys}
    for row in label_rows:
        key = (str(row["workflow_id"]), str(row["note_id"]))
        if key in wanted_keys:
            labels_by_key[key].append(str(row["label"]))

    return [
        {
            "workflow_id": str(row_by_key[key]["workflow_id"]),
            "note_id": str(row_by_key[key]["note_id"]),
            "labels": sorted(set(labels_by_key.get(key, []))),
        }
        for key in sliced_keys
    ]
