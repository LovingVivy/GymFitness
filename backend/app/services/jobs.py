"""Reading background job status. Jobs are only visible to whoever requested them."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.repositories import jobs as jobs_repository
from app.schemas.jobs import JobResponse
from app.services.pt import error

FILES_PREFIX = "/api/v1/files/"


def _to_job(row: Mapping[str, Any]) -> JobResponse:
    file_id = row.get("result_file_id")
    return JobResponse(
        id=row["id"],
        job_type=row["job_type"],
        status=row["status"],
        progress=int(row.get("progress") or 0),
        error_message=row.get("error_message"),
        created_at=row["created_at"],
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        file_id=file_id,
        file_name=row.get("file_name"),
        file_size=row.get("file_size"),
        download_url=f"{FILES_PREFIX}{file_id}" if file_id else None,
    )


def get_job(db: Session, user: Mapping[str, Any], job_id: str) -> JobResponse:
    row = jobs_repository.get(db, job_id)
    if row is None or row.get("requested_by") != user["id"]:
        raise error(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND", "Không tìm thấy tác vụ.")
    return _to_job(row)


def list_jobs(
    db: Session, user: Mapping[str, Any], type_prefix: str | None, limit: int
) -> list[JobResponse]:
    rows = jobs_repository.list_for_user(db, user["id"], type_prefix=type_prefix, limit=limit)
    return [_to_job(row) for row in rows]
