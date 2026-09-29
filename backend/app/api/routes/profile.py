"""Profile endpoints for the authenticated member."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, DbDep
from app.schemas.profile import AvatarUploadRequest, ProfileResponse, ProfileUpdateRequest
from app.services import profile as profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse, summary="Hồ sơ hội viên hiện tại")
def read_profile(user: CurrentUserDep, db: DbDep) -> ProfileResponse:
    """Thông tin cá nhân, ảnh đại diện, hồ sơ hội viên và gói đang đăng ký."""
    return profile_service.get_profile(db, user["id"])


@router.patch("", response_model=ProfileResponse, summary="Cập nhật hồ sơ hội viên")
def update_profile(
    payload: ProfileUpdateRequest,
    user: CurrentUserDep,
    db: DbDep,
) -> ProfileResponse:
    """Cập nhật thông tin cá nhân, thể chất và mục tiêu. Trường bỏ trống giữ nguyên."""
    return profile_service.update_profile(db, user["id"], payload)


@router.post(
    "/avatar",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Cập nhật ảnh đại diện",
)
def upload_avatar(
    payload: AvatarUploadRequest,
    user: CurrentUserDep,
    db: DbDep,
) -> ProfileResponse:
    """Nhận ảnh dạng data URL, lưu ra storage nội bộ và gắn vào hồ sơ."""
    return profile_service.save_avatar(db, user["id"], data_url=payload.image)
