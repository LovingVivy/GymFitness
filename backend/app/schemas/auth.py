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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
