"""Business logic for note lifecycle in ai-datastore."""
from __future__ import annotations

from datetime import datetime, timezone

from . import filesystem, repository, validators
from .models import SearchNotesResponse
from .search_dsl import normalize_query


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DatastoreService:
    """Coordinates validation, file writes, and CSV metadata operations."""

    async def _ensure_ready(self) -> None:
        await repository.ensure_schema()

    async def _generate_note_id(self, workflow_id: str) -> str:
        existing_ids = await repository.list_note_ids_for_workflow(workflow_id)
        max_seen = 0
        for raw_id in existing_ids:
            if raw_id.isdigit():
                max_seen = max(max_seen, int(raw_id))
        return str(max_seen + 1)

    async def upsert_note(
        self,
        workflow_id: str,
        note_description: str,
        labels: list[str],
        name: str,
        filename_hint: str | None = None,
        note_id: str | None = None,
        content: str | None = None,
        file_path: str | None = None,
    ) -> dict:
        wf = validators.validate_workflow_id(workflow_id)
        description = validators.validate_note_description(note_description)
        normalized_labels = validators.normalize_labels(labels)
        note_name = validators.validate_required_note_name(name)
        normalized_filename_hint = validators.validate_optional_filename_hint(filename_hint)
        content, file_path = validators.validate_content_or_file_path(content, file_path)

        await self._ensure_ready()
        id_source = "caller"
        if note_id is None:
            nid = await self._generate_note_id(wf)
            existing = None
            id_source = "system"
        else:
            nid = validators.validate_note_id(note_id)
            existing = await repository.get_note_by_key(wf, nid)

        source_kind = "content"
        note_content: str
        if content is not None:
            note_content = content
        else:
            assert file_path is not None
            source_kind = "file_path"
            note_content = await filesystem.read_source_content(file_path)

        target_rel_path = filesystem.build_note_rel_path(
            wf,
            nid,
            note_name,
            normalized_filename_hint,
        )
        rel_path = await filesystem.write_note_content_at_path(target_rel_path, note_content)
        if existing is not None and existing.rel_path != rel_path:
            await filesystem.delete_relative_path(existing.rel_path)
        record, applied_labels = await repository.upsert_note_metadata(
            workflow_id=wf,
            note_id=nid,
            note_description=description,
            rel_path=rel_path,
            labels=normalized_labels,
            now_iso=_now_iso(),
        )
        return {
            "status": "ok",
            "source": source_kind,
            "id_source": id_source,
            "workflow_id": wf,
            "note_id": nid,
            "note_description": description,
            "name": note_name,
            "filename_hint": normalized_filename_hint,
            "labels": applied_labels,
            "rel_path": rel_path,
            "note": record.to_dict(),
        }

    async def delete_note(self, workflow_id: str, note_id: str) -> dict:
        wf = validators.validate_workflow_id(workflow_id)
        nid = validators.validate_note_id(note_id)
        await self._ensure_ready()

        existing = await repository.get_note_by_key(wf, nid)
        if existing is None:
            raise ValueError(f"note not found: workflow_id={wf!r} note_id={nid!r}")

        await filesystem.delete_relative_path(existing.rel_path)
        deleted = await repository.delete_note_metadata(wf, nid)
        await repository.prune_unreferenced_labels()
        await filesystem.remove_workflow_dir_if_empty(wf)

        if deleted is None:
            raise RuntimeError("delete_note lost metadata unexpectedly")
        return {
            "status": "ok",
            "deleted": True,
            "workflow_id": wf,
            "note_id": nid,
            "rel_path": deleted.rel_path,
        }

    async def delete_label(self, label: str) -> dict:
        normalized = validators.validate_label(label)
        await self._ensure_ready()

        label_result = await repository.delete_label_and_collect_unlabeled(normalized)
        if not label_result["label_found"]:
            return {
                "status": "ok",
                "label": normalized,
                "label_found": False,
                "detached_links": 0,
                "garbage_collected_notes": 0,
                "next_action": "No-op; label does not exist.",
            }

        orphan_notes = label_result["unlabeled_notes"]
        for note in orphan_notes:
            await filesystem.delete_relative_path(note.rel_path)

        deleted_rows = await repository.delete_notes_by_keys(
            [(n.workflow_id, n.note_id) for n in orphan_notes]
        )
        await repository.prune_unreferenced_labels()

        workflow_ids = sorted({n.workflow_id for n in orphan_notes})
        for workflow_id in workflow_ids:
            await filesystem.remove_workflow_dir_if_empty(workflow_id)

        return {
            "status": "ok",
            "label": normalized,
            "label_found": True,
            "detached_links": int(label_result["detached_links"]),
            "garbage_collected_notes": deleted_rows,
            "garbage_collected_note_ids": [n.note_id for n in orphan_notes],
        }

    async def get_note(self, workflow_id: str, note_id: str) -> dict:
        wf = validators.validate_workflow_id(workflow_id)
        nid = validators.validate_note_id(note_id)
        await self._ensure_ready()

        record = await repository.get_note_by_key(wf, nid)
        if record is None:
            raise ValueError(f"note not found: workflow_id={wf!r} note_id={nid!r}")
        labels = await repository.list_labels_for_note(wf, nid)
        content = await filesystem.read_note_content_at_path(record.rel_path)
        return {
            "status": "ok",
            "workflow_id": wf,
            "note_id": nid,
            "labels": labels,
            "rel_path": record.rel_path,
            "note_description": record.note_description,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "content": content,
            "note": record.to_dict(),
        }

    async def get_labels(self, workspace_id: str | None = None) -> dict:
        await self._ensure_ready()
        workflow_id = validators.validate_optional_workflow_id(workspace_id)
        labels = await repository.list_unique_labels(workflow_id=workflow_id)
        return {
            "workspace_id": workflow_id,
            "labels": labels,
        }

    async def _search_notes(
        self,
        workflow_id: str | None,
        query: dict | None,
        limit: int = 200,
        offset: int = 0,
    ) -> SearchNotesResponse:
        await self._ensure_ready()
        wf = validators.validate_optional_workflow_id(workflow_id)
        limit, offset = validators.validate_limit_offset(limit, offset)
        normalized = normalize_query(query) if query is not None else None
        matches = await repository.search_note_identifiers(
            workflow_id=wf,
            expr=normalized,
            limit=limit,
            offset=offset,
        )
        return {"matches": matches}

    async def search_notes_by_label(
        self,
        workflow_id: str | None,
        query: dict,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> SearchNotesResponse:
        return await self._search_notes(
            workflow_id=workflow_id,
            query=query,
            limit=limit,
            offset=offset,
        )

    async def search_notes_by_workflow_id(
        self,
        workflow_id: str,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> SearchNotesResponse:
        return await self._search_notes(
            workflow_id=workflow_id,
            query=None,
            limit=limit,
            offset=offset,
        )
