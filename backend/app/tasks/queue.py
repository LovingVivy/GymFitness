"""Background job queue for slow work: sending email, building large exports.

MySQL (``background_jobs``) is the source of truth for every job and its
status; Redis only carries job ids to the worker process. When Redis is not
reachable the job runs in a small thread pool inside the API instead, so
nothing is lost on a laptop without Redis. ``JOB_QUEUE_MODE=inline`` runs jobs
synchronously, which the test suite uses for determinism.

    job_id = queue.enqueue(db, "export.report", {...}, requested_by=user_id)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.redis_client import get_redis, mark_unavailable
from app.db.base import new_uuid
from app.db.session import SessionLocal
from app.repositories import jobs as jobs_repository

logger = logging.getLogger(__name__)

QUEUE_KEY = "gf:jobs"

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gf-job")


@dataclass
class JobContext:
    db: Session
    job_id: str
    job_type: str
    requested_by: str | None
    parameters: dict[str, Any]

    def progress(self, value: int) -> None:
        jobs_repository.progress(self.db, self.job_id, value)


Handler = Callable[[JobContext], str | None]
_handlers: dict[str, Handler] = {}


def handler(job_type: str) -> Callable[[Handler], Handler]:
    """Register the function that runs jobs of ``job_type``; it may return a file id."""

    def register(function: Handler) -> Handler:
        _handlers[job_type] = function
        return function

    return register


def _load_handlers() -> None:
    # Import muộn để services có thể import queue mà không vòng lặp.
    from app.tasks import handlers  # noqa: F401


def enqueue(
    db: Session, job_type: str, parameters: dict[str, Any], requested_by: str | None = None
) -> str:
    job_id = new_uuid()
    jobs_repository.create(
        db, job_id=job_id, job_type=job_type, requested_by=requested_by, parameters=parameters
    )
    dispatch(job_id)
    return job_id


def dispatch(job_id: str) -> None:
    mode = get_settings().job_queue_mode.strip().lower()
    if mode == "inline":
        run(job_id)
        return
    if mode in ("auto", "redis"):
        client = get_redis()
        if client is not None:
            try:
                client.rpush(QUEUE_KEY, job_id)
                return
            except redis.RedisError as exc:
                mark_unavailable(exc)
        if mode == "redis":
            logger.warning("Redis không khả dụng; worker sẽ chạy bù tác vụ %s.", job_id)
            return
    _executor.submit(run, job_id)


def run(job_id: str) -> None:
    """Claim and execute one job; never raises."""
    _load_handlers()
    try:
        with SessionLocal() as db:
            job = jobs_repository.claim(db, job_id)
            if job is None:
                return
            context = JobContext(
                db=db,
                job_id=job_id,
                job_type=job["job_type"],
                requested_by=job.get("requested_by"),
                parameters=job.get("parameters") or {},
            )
            log = {"job_id": job_id, "job_type": context.job_type}
            function = _handlers.get(context.job_type)
            if function is None:
                jobs_repository.finish(
                    db, job_id, succeeded=False, error_message="Loại tác vụ không được hỗ trợ."
                )
                logger.error("Không có handler cho tác vụ", extra=log)
                return
            try:
                result_file_id = function(context)
            except Exception as exc:  # noqa: BLE001 - mọi lỗi đều phải ghi vào job
                db.rollback()
                logger.exception("Tác vụ thất bại", extra=log)
                jobs_repository.finish(db, job_id, succeeded=False, error_message=str(exc)[:500])
                return
            jobs_repository.finish(db, job_id, succeeded=True, result_file_id=result_file_id)
            logger.info("Tác vụ hoàn tất", extra=log)
    except Exception:  # noqa: BLE001 - lỗi kết nối database
        logger.exception("Không chạy được tác vụ", extra={"job_id": job_id})
