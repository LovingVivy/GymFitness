"""Worker process: takes job ids from Redis and runs them.

    python -m app.tasks.worker

Also re-runs jobs left PENDING for more than two minutes (Redis restarted,
API pushed while the worker was down...), and keeps working off that sweep
alone while Redis is unavailable.
"""

from __future__ import annotations

import logging
import signal
import time
from datetime import timedelta

import redis

from app.core.config import get_settings
from app.core.gym_time import now_utc, to_naive_utc
from app.core.logging import configure_logging
from app.core.redis_client import get_redis, mark_unavailable
from app.db.session import SessionLocal
from app.repositories import jobs as jobs_repository
from app.tasks import maintenance
from app.tasks.queue import QUEUE_KEY, run

logger = logging.getLogger("app.tasks.worker")

SWEEP_SECONDS = 60
STALE_AFTER = timedelta(minutes=2)

_stopping = False


def _stop(signum: int, _frame: object) -> None:
    global _stopping
    _stopping = True
    logger.info("Nhận tín hiệu %s, worker dừng sau tác vụ hiện tại.", signum)


def sweep() -> int:
    with SessionLocal() as db:
        job_ids = jobs_repository.pending_before(db, to_naive_utc(now_utc() - STALE_AFTER))
    for job_id in job_ids:
        run(job_id)
    return len(job_ids)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.json_logs)
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    logger.info("Worker đã khởi động.")

    last_sweep = 0.0
    last_maintenance = 0.0
    while not _stopping:
        if time.monotonic() - last_maintenance > settings.maintenance_interval_seconds:
            try:
                maintenance.run_once()
            except Exception:  # noqa: BLE001 - database tạm mất kết nối
                logger.exception("Bảo trì định kỳ thất bại.")
            last_maintenance = time.monotonic()

        if time.monotonic() - last_sweep > SWEEP_SECONDS:
            try:
                recovered = sweep()
                if recovered:
                    logger.info("Đã chạy bù %s tác vụ tồn đọng.", recovered)
            except Exception:  # noqa: BLE001 - database tạm mất kết nối
                logger.exception("Không quét được tác vụ tồn đọng.")
            last_sweep = time.monotonic()

        client = get_redis()
        if client is None:
            time.sleep(5)
            continue
        try:
            item = client.blpop([QUEUE_KEY], timeout=5)
        except redis.RedisError as exc:
            mark_unavailable(exc)
            time.sleep(2)
            continue
        if item:
            run(item[1])

    logger.info("Worker đã dừng.")


if __name__ == "__main__":
    main()
