from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUserDep
from app.db.session import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    TwoFactorChallenge,
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbDep) -> TokenResponse:
    return auth_service.register(db, payload)


@router.post(
    "/login",
    response_model=TokenResponse | TwoFactorChallenge,
    summary="Đăng nhập bằng email hoặc tên đăng nhập",
)
def login(payload: LoginRequest, db: DbDep) -> TokenResponse | TwoFactorChallenge:
    """Tài khoản bật xác thực 2 bước nhận ``challenge_token`` thay cho access token."""
    return auth_service.login(db, payload)


@router.post(
    "/2fa/verify", response_model=TokenResponse, summary="Bước 2 của đăng nhập: mã xác thực"
)
def verify_two_factor(payload: TwoFactorVerifyRequest, db: DbDep) -> TokenResponse:
    return auth_service.verify_two_factor(db, payload)


@router.post(
    "/2fa/setup",
    response_model=TwoFactorSetupResponse,
    summary="Tạo khoá xác thực 2 bước (chưa bật)",
)
def setup_two_factor(user: CurrentUserDep, db: DbDep) -> TwoFactorSetupResponse:
    """Trả mã QR cho ứng dụng Authenticator; chỉ bật sau khi gọi ``/2fa/enable`` với mã đúng."""
    return auth_service.setup_two_factor(db, user)


@router.post("/2fa/enable", response_model=MessageResponse, summary="Bật xác thực 2 bước")
def enable_two_factor(
    payload: TwoFactorEnableRequest, user: CurrentUserDep, db: DbDep
) -> MessageResponse:
    return auth_service.enable_two_factor(db, user, payload)


@router.post("/2fa/disable", response_model=MessageResponse, summary="Tắt xác thực 2 bước")
def disable_two_factor(
    payload: TwoFactorDisableRequest, user: CurrentUserDep, db: DbDep
) -> MessageResponse:
    """Cần cả mật khẩu và mã hiện tại để tránh bị tắt khi lộ phiên đăng nhập."""
    return auth_service.disable_two_factor(db, user, payload)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Gửi email đặt lại mật khẩu",
)
def forgot_password(payload: ForgotPasswordRequest, db: DbDep) -> MessageResponse:
    """Luôn trả 202 để không lộ email nào đã đăng ký. Email được gửi qua hàng đợi tác vụ."""
    return auth_service.forgot_password(db, payload)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Đặt mật khẩu mới bằng token trong email",
)
def reset_password(payload: ResetPasswordRequest, db: DbDep) -> MessageResponse:
    return auth_service.reset_password(db, payload)
