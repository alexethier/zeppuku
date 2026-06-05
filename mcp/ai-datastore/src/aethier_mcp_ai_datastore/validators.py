"""Input validation helpers for ai-datastore tools."""
from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
NOTE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SLUG_SAFE_RE = re.compile(r"[^A-Za-z0-9]+")
NOTE_NAME_CLEAN_RE = re.compile(r"[^A-Za-z0-9._ -]+")
NOTE_NAME_WS_RE = re.compile(r"\s+")

ALLOWED_SOURCE_ROOT = Path("/Users/aethier/playground")


def validate_workflow_id(workflow_id: str) -> str:
    workflow_id = workflow_id.strip()
    if not WORKFLOW_ID_RE.match(workflow_id):
        raise ValueError(
            f"invalid workflow_id {workflow_id!r}: "
            "must match [A-Za-z0-9][A-Za-z0-9._-]{1,127}"
        )
    return workflow_id


def validate_note_id(note_id: str) -> str:
    note_id = note_id.strip()
    if not NOTE_ID_RE.match(note_id):
        raise ValueError(
            f"invalid note_id {note_id!r}: "
            "must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}"
        )
    return note_id


def validate_note_description(note_description: str) -> str:
    note_description = note_description.strip()
    if not note_description:
        raise ValueError("note_description must be non-empty")
    if len(note_description) > 500:
        raise ValueError("note_description must be <= 500 chars")
    return note_description


def validate_required_note_name(name: str) -> str:
    trimmed = name.strip()
    if not trimmed:
        raise ValueError("name must be non-empty")
    if len(trimmed) > 200:
        raise ValueError("name must be <= 200 chars")

    # Keep a human-readable name while cleansing punctuation/noise characters.
    cleansed = NOTE_NAME_CLEAN_RE.sub(" ", trimmed)
    cleansed = NOTE_NAME_WS_RE.sub(" ", cleansed).strip(" .-_")
    if not cleansed:
        raise ValueError("name must contain at least one letter or digit")
    if len(cleansed) < 3:
        raise ValueError("name must be at least 3 chars after cleansing")
    return cleansed[:80].rstrip(" .-_")


def validate_optional_filename_hint(filename_hint: str | None) -> str | None:
    if filename_hint is None:
        return None
    trimmed = filename_hint.strip()
    if not trimmed:
        raise ValueError("filename_hint must be non-empty when provided")
    if len(trimmed) > 120:
        raise ValueError("filename_hint must be <= 120 chars")
    cleansed = NOTE_NAME_CLEAN_RE.sub(" ", trimmed)
    cleansed = NOTE_NAME_WS_RE.sub(" ", cleansed).strip(" .-_")
    if not cleansed:
        raise ValueError("filename_hint must contain at least one letter or digit")
    return cleansed[:40].rstrip(" .-_")


def slugify_note_name(name: str) -> str:
    slug = SLUG_SAFE_RE.sub("-", name).strip("-").lower()
    if not slug:
        raise ValueError("name must contain at least one letter or digit")
    return slug[:80]


def slugify_filename_hint(filename_hint: str) -> str:
    slug = SLUG_SAFE_RE.sub("-", filename_hint).strip("-").lower()
    if not slug:
        raise ValueError("filename_hint must contain at least one letter or digit")
    return slug[:40]


def normalize_labels(labels: list[str]) -> list[str]:
    if not labels:
        raise ValueError("labels must be non-empty")
    out: list[str] = []
    seen: set[str] = set()
    for raw in labels:
        label = raw.strip().lower()
        if not LABEL_RE.match(label):
            raise ValueError(
                f"invalid label {raw!r}: "
                "must match [A-Za-z0-9][A-Za-z0-9._:-]{0,127}"
            )
        if label not in seen:
            seen.add(label)
            out.append(label)
    if not out:
        raise ValueError("labels must contain at least one valid label")
    return out


def validate_label(label: str) -> str:
    normalized = label.strip().lower()
    if not LABEL_RE.match(normalized):
        raise ValueError(
            f"invalid label {label!r}: "
            "must match [A-Za-z0-9][A-Za-z0-9._:-]{0,127}"
        )
    return normalized


def validate_optional_content_or_file_path(
    content: str | None, file_path: str | None
) -> tuple[str | None, str | None]:
    # Optional source: callers may omit both; if provided, only one is allowed.
    if content is not None and file_path is not None:
        raise ValueError("at most one of content or file_path may be provided")

    if content is not None:
        if not content.strip():
            raise ValueError("content must be non-empty")
        return content, None

    if file_path is None:
        return None, None

    p = Path(file_path).expanduser()
    if not p.is_absolute():
        raise ValueError("file_path must be absolute")
    return None, str(p)
def validate_optional_workflow_id(workflow_id: str | None) -> str | None:
    if workflow_id is None:
        return None
    return validate_workflow_id(workflow_id)


def validate_limit_offset(limit: int, offset: int) -> tuple[int, int]:
    if not isinstance(limit, int) or not (1 <= limit <= 1000):
        raise ValueError(f"invalid limit {limit!r}: must be integer 1..1000")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError(f"invalid offset {offset!r}: must be integer >= 0")
    return limit, offset
