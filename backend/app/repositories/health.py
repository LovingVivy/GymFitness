"""Database liveness check. The SQL lives in ``database/11_platform.sql``."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.procedures import call

PING = "sp_health_ping"


def ping(db: Session) -> None:
    """Raise ``SQLAlchemyError`` when MySQL does not answer."""
    call(db, PING, {})
