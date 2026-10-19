"""Shared FastAPI dependencies, including bearer-token authentication."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.permissions import Permission, has_permission
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole, UserStatus
from app.repositories import auth as auth_repository

DbDep = Annotated[Session, Depends(get_db)]

bearer_scheme = HTTPBearer(auto_error=False)

CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": {}}},
    )


def get_current_user(request: Request, db: DbDep, credentials: CredentialsDep) -> dict[str, Any]:
    """Resolve the authenticated account from the ``Authorization`` header.

    The backend is the only layer that decides access; the frontend merely
    hides or shows UI.
    """
    if credentials is None or not credentials.credentials:
        raise _error(
            status.HTTP_401_UNAUTHORIZED, "NOT_AUTHENTICATED", "Cần đăng nhập để tiếp tục."
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise _error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_TOKEN",
            "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
        ) from exc

    user = auth_repository.find_user_by_id(db, str(payload.get("sub", "")))
    if user is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "Tài khoản không tồn tại.")

    if user["status"] in (UserStatus.SUSPENDED.value, UserStatus.INACTIVE.value):
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "ACCOUNT_DISABLED",
            "Tài khoản đã bị khoá hoặc ngưng hoạt động.",
        )

    # Cho access log biết ai gọi request.
    request.state.user_id = user["id"]
    return user


CurrentUserDep = Annotated[dict[str, Any], Depends(get_current_user)]


def require_trainer(user: CurrentUserDep) -> dict[str, Any]:
    """Guard for endpoints only a personal trainer may call."""
    if user["role"] != UserRole.PT.value:
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Chỉ huấn luyện viên mới dùng được chức năng này.",
        )
    return user


TrainerDep = Annotated[dict[str, Any], Depends(require_trainer)]


def require_admin(user: CurrentUserDep) -> dict[str, Any]:
    """Guard for the admin area."""
    if user["role"] != UserRole.ADMIN.value:
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Chỉ quản trị viên mới dùng được chức năng này.",
        )
    return user


AdminDep = Annotated[dict[str, Any], Depends(require_admin)]


def require_permission(permission: Permission):
    """Dependency factory: the caller's role must grant ``permission`` (403 otherwise)."""

    def guard(user: CurrentUserDep) -> dict[str, Any]:
        if not has_permission(user["role"], permission):
            raise _error(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Tài khoản của bạn không có quyền thực hiện thao tác này.",
            )
        return user

    return guard


def PermissionDep(permission: Permission) -> Any:  # noqa: N802 - dùng như một kiểu
    """``user: PermissionDep(Permission.PAYMENTS_VOID)`` in a route signature."""
    return Annotated[dict[str, Any], Depends(require_permission(permission))]
