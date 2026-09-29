"""Shared helper for invoking MySQL stored procedures.

No module in this package contains a ``SELECT``/``INSERT``/``UPDATE`` of its
own: every statement lives in ``database/03_procedures.sql`` and is reached
through :func:`call`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class ProcedureOutcome:
    """Result set carrying ``error_code``/``error_message`` plus extra columns."""

    error_code: str | None
    error_message: str | None
    data: dict[str, Any]

    @property
    def succeeded(self) -> bool:
        return self.error_code is None


def outcome_from(rows: list[dict[str, Any]], *extra_keys: str) -> ProcedureOutcome:
    """Build a :class:`ProcedureOutcome` from the first row of a result set."""
    if not rows:
        return ProcedureOutcome(INTERNAL_ERROR, "Lỗi hệ thống.", {})
    row = rows[0]
    return ProcedureOutcome(
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        data={key: row.get(key) for key in extra_keys},
    )


def call(db: Session, procedure: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    """Invoke ``procedure`` and return its rows as dictionaries.

    ``procedure`` is always a module-level constant owned by a repository
    module — never a value derived from a request — so building the CALL text
    here cannot be influenced from outside. Values always travel as bind
    parameters.
    """
    placeholders = ", ".join(f":{name}" for name in parameters)
    result = db.execute(text(f"CALL {procedure}({placeholders})"), parameters)
    try:
        if not result.returns_rows:
            return []
        return [dict(row) for row in result.mappings().all()]
    finally:
        result.close()
