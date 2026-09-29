"""Membership endpoints: plan catalogue and subscriptions.

Payment confirmation lives in :mod:`app.api.routes.payments`.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, DbDep
from app.schemas.profile import (
    PlanResponse,
    SubscriptionCreateRequest,
    SubscriptionCreateResponse,
)
from app.services import profile as profile_service

router = APIRouter(tags=["membership"])


@router.get("/plans", response_model=list[PlanResponse], summary="Danh sách gói tập đang mở bán")
def list_plans(db: DbDep) -> list[PlanResponse]:
    return profile_service.list_plans(db)


@router.post(
    "/subscriptions",
    response_model=SubscriptionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo đăng ký gói (payment PENDING)",
)
def create_subscription(
    payload: SubscriptionCreateRequest,
    user: CurrentUserDep,
    db: DbDep,
) -> SubscriptionCreateResponse:
    """Tạo payment PENDING và subscription PENDING. Chưa kích hoạt quyền lợi."""
    return profile_service.create_subscription(db, user, payload.plan_id, payload.pt_sessions)
