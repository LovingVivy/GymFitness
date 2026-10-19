"""Data access for background jobs and generated files (``database/11_platform.sql``)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.procedures import call

CREATE = "sp_job_create"
CLAIM = "sp_job_claim"
PROGRESS = "sp_job_progress"
FINISH = "sp_job_finish"
GET = "sp_job_get"
LIST = "sp_job_list"
PENDING = "sp_job_pending_list"
SAVE_FILE = "sp_file_save"


def _parse(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    parameters = row.get("parameters")
    if isinstance(parameters, (str, bytes, bytearray)):
        row["parameters"] = json.loads(parameters or "{}")
    return row


def create(
    db: Session, *, job_id: str, job_type: str, requested_by: str | None, parameters: dict
) -> None:
    call(
        db,
        CREATE,
        {
            "p_job_id": job_id,
            "p_job_type": job_type,
            "p_requested_by": requested_by,
            "p_parameters": json.dumps(parameters, ensure_ascii=False, default=str),
        },
    )


def claim(db: Session, job_id: str) -> dict[str, Any] | None:
    """Move PENDING → RUNNING; ``None`` when another worker already took it."""
    rows = call(db, CLAIM, {"p_job_id": job_id})
    row = _parse(rows[0]) if rows else None
    return row if row and row.get("claimed") else None


def progress(db: Session, job_id: str, value: int) -> None:
    call(db, PROGRESS, {"p_job_id": job_id, "p_progress": value})


def finish(
    db: Session,
    job_id: str,
    *,
    succeeded: bool,
    result_file_id: str | None = None,
    error_message: str | None = None,
) -> None:
    call(
        db,
        FINISH,
        {
            "p_job_id": job_id,
            "p_status": "SUCCESS" if succeeded else "FAILED",
            "p_result_file_id": result_file_id,
            "p_error_message": error_message,
        },
    )


def get(db: Session, job_id: str) -> dict[str, Any] | None:
    rows = call(db, GET, {"p_job_id": job_id})
    return _parse(rows[0]) if rows else None


def list_for_user(
    db: Session, user_id: str, *, type_prefix: str | None, limit: int
) -> list[dict[str, Any]]:
    rows = call(
        db, LIST, {"p_requested_by": user_id, "p_type_prefix": type_prefix, "p_limit": limit}
    )
    return [_parse(row) for row in rows]


def pending_before(db: Session, created_before: datetime, limit: int = 50) -> list[str]:
    rows = call(db, PENDING, {"p_created_before": created_before, "p_limit": limit})
    return [row["id"] for row in rows]


def save_file(
    db: Session,
    *,
    file_id: str,
    owner_user_id: str | None,
    storage_key: str,
    original_name: str,
    content_type: str,
    size_bytes: int,
    checksum_sha256: str,
) -> None:
    call(
        db,
        SAVE_FILE,
        {
            "p_file_id": file_id,
            "p_owner_user_id": owner_user_id,
            "p_storage_key": storage_key,
            "p_original_name": original_name,
            "p_content_type": content_type,
            "p_size_bytes": size_bytes,
            "p_checksum_sha256": checksum_sha256,
        },
    )
