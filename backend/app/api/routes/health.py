from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.redis_client import redis_status
from app.db.session import SessionLocal
from app.repositories import health as health_repository
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


def ping_database() -> None:
    with SessionLocal() as db:
        health_repository.ping(db)


@router.get("/live", response_model=HealthResponse, response_model_exclude_none=True)
def live() -> HealthResponse:
    return HealthResponse(status="alive")


@router.get("/ready", response_model=HealthResponse)
def ready() -> HealthResponse:
    """MySQL is required; Redis is reported but optional (the API degrades without it)."""
    try:
        ping_database()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc
    return HealthResponse(status="ready", checks={"database": "up", "redis": redis_status()})
