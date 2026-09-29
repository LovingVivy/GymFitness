"""Startup guards on security-sensitive settings."""

from __future__ import annotations

import secrets

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**values) -> Settings:
    # _env_file=None: kiểm tra đúng giá trị truyền vào, không đọc backend/.env.
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "secret",
    ["", "dev-secret-change-me", "change-me-to-a-long-random-secret", "short-but-random-1234"],
)
def test_production_refuses_weak_jwt_secret(secret: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        _settings(app_env="production", jwt_secret_key=secret)


def test_production_accepts_strong_jwt_secret() -> None:
    secret = secrets.token_urlsafe(64)
    assert _settings(app_env="production", jwt_secret_key=secret).jwt_secret_key == secret


def test_development_never_signs_with_empty_secret() -> None:
    settings = _settings(app_env="development", jwt_secret_key="")
    assert len(settings.jwt_secret_key) >= 32


def test_payment_simulation_defaults_follow_environment() -> None:
    strong = secrets.token_urlsafe(64)
    assert _settings(app_env="development").allow_payment_simulation is True
    assert _settings(app_env="production", jwt_secret_key=strong).allow_payment_simulation is False
    assert (
        _settings(
            app_env="production", jwt_secret_key=strong, payment_simulation_enabled=True
        ).allow_payment_simulation
        is True
    )
