"""Typed models for the ai-datastore service layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


@dataclass(frozen=True)
class NoteRecord:
    workflow_id: str
    note_id: str
    note_description: str
    rel_path: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: dict) -> "NoteRecord":
        return cls(
            workflow_id=str(row["workflow_id"]),
            note_id=str(row["note_id"]),
            note_description=str(row["note_description"]),
            rel_path=str(row["rel_path"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "note_id": self.note_id,
            "note_description": self.note_description,
            "rel_path": self.rel_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SearchNoteMatch(TypedDict):
    workflow_id: str
    note_id: str
    labels: list[str]


class SearchNotesResponse(TypedDict):
    matches: list[SearchNoteMatch]
