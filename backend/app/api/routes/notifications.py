"""In-app notification endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, DbDep
from app.schemas.pt import NotificationListResponse
from app.services import pt as pt_service

router = APIRouter(prefix="/notifications", tags=["notifications"])

LimitQuery = Annotated[int, Query(ge=1, le=100, description="Số thông báo tối đa")]


@router.get("", response_model=NotificationListResponse, summary="Thông báo của tôi")
def list_notifications(
    user: CurrentUserDep,
    db: DbDep,
    limit: LimitQuery = 30,
) -> NotificationListResponse:
    return pt_service.list_notifications(db, user["id"], limit)


@router.get("/unread-count", summary="Số thông báo chưa đọc")
def unread_count(user: CurrentUserDep, db: DbDep) -> dict:
    return {"unread": pt_service.unread_notifications(db, user["id"])}


@router.post("/read-all", response_model=NotificationListResponse, summary="Đánh dấu tất cả đã đọc")
def mark_all_read(user: CurrentUserDep, db: DbDep) -> NotificationListResponse:
    return pt_service.mark_all_notifications_read(db, user["id"])


@router.post(
    "/{notification_id}/read", response_model=NotificationListResponse, summary="Đánh dấu đã đọc"
)
def mark_read(notification_id: str, user: CurrentUserDep, db: DbDep) -> NotificationListResponse:
    return pt_service.mark_notification_read(db, user["id"], notification_id)
