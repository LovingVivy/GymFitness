from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["alive", "ready"]
    # Trạng thái từng phụ thuộc, vd. {"database": "up", "redis": "down"}.
    checks: dict[str, str] | None = None
