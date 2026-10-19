from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: str
    phone: str | None = None
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def _strip_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Họ và tên không được để trống")
        return value

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Email không hợp lệ")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    phone: str | None = None
    role: str
    status: str
    full_name: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    experience_level: str | None = None
    fitness_goal: str | None = None
    weekly_training_sessions: int | None = None
    # Quyền theo vai trò (RBAC), frontend dùng để ẩn/hiện màn hình và nút.
    permissions: list[str] = Field(default_factory=list)
    two_factor_enabled: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TwoFactorChallenge(BaseModel):
    """Password was right but the account has 2FA: send the code to ``/2fa/verify``."""

    two_factor_required: Literal[True] = True
    challenge_token: str
    expires_in: int


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("Email không hợp lệ")
    return value


class ForgotPasswordRequest(BaseModel):
    email: str = Field(max_length=254)

    _email = field_validator("email")(_normalize_email)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class TwoFactorVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=20, max_length=2000)
    code: str = Field(min_length=6, max_length=10)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg: str
    setup_token: str


class TwoFactorEnableRequest(BaseModel):
    setup_token: str = Field(min_length=20, max_length=4000)
    code: str = Field(min_length=6, max_length=10)


class TwoFactorDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=10)
