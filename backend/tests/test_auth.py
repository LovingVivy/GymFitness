"""Integration and unit tests for registration and login.

The integration tests talk to the real MySQL instance because every statement
of this feature lives in a stored procedure — mocking the database would test
nothing. The ``db`` and ``account`` fixtures come from ``conftest.py`` and
remove everything a flow created.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app

client = TestClient(app)
settings = get_settings()

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PASSWORD = "password123"


def _register(account: dict[str, str], **overrides):
    payload = {
        "full_name": "Pytest User",
        "email": account["email"],
        "phone": account["phone"],
        "password": account["password"],
    }
    payload.update(overrides)
    return client.post(REGISTER_URL, json=payload)


# --------------------------------------------------------------------------
# Password hashing and JWT (unit, no database)
# --------------------------------------------------------------------------


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password(PASSWORD)
    second = hash_password(PASSWORD)
    assert first != second, "mỗi lần băm phải dùng salt ngẫu nhiên"
    assert first.startswith("pbkdf2_sha256$")
    assert verify_password(PASSWORD, first)
    assert not verify_password("sai-mat-khau", first)


def test_verify_password_rejects_malformed_hash() -> None:
    assert not verify_password(PASSWORD, "khong-phai-hash")
    assert not verify_password(PASSWORD, "argon2$1$a$b")


def test_access_token_round_trip() -> None:
    token = create_access_token("user-1", "USER")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "USER"
    assert payload["exp"] > payload["iat"]


def test_access_token_rejects_tampered_signature() -> None:
    token = create_access_token("user-1", "USER")
    header, body, signature = token.split(".")
    forged = f"{header}.{body}.{signature[:-4]}AAAA"
    with pytest.raises(ValueError):
        decode_access_token(forged)


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def test_register_creates_account_and_returns_token(account, db) -> None:
    response = _register(account)
    assert response.status_code == 201

    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == account["email"]
    assert body["user"]["phone"] == account["phone"]
    assert body["user"]["full_name"] == "Pytest User"
    assert body["user"]["role"] == "USER"
    assert body["user"]["status"] == "ACTIVE"

    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == body["user"]["id"]

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM users u JOIN user_profiles p ON p.user_id = u.id "
            "WHERE u.email = %s AND p.full_name = %s",
            (account["email"], "Pytest User"),
        )
        assert cursor.fetchone()[0] == 1, "phải tạo cả users lẫn user_profiles"


def test_register_never_stores_plaintext_password(account, db) -> None:
    _register(account)
    with db.cursor() as cursor:
        cursor.execute("SELECT password_hash FROM users WHERE email = %s", (account["email"],))
        stored = cursor.fetchone()[0]
    assert stored != account["password"]
    assert verify_password(account["password"], stored)


def test_register_normalises_email_case(account, db) -> None:
    response = _register(account, email=account["email"].upper())
    assert response.status_code == 201
    assert response.json()["user"]["email"] == account["email"]


def test_register_without_phone_is_allowed(account, db) -> None:
    response = _register(account, phone=None)
    assert response.status_code == 201
    assert response.json()["user"]["phone"] is None


def test_register_rejects_duplicate_email(account) -> None:
    assert _register(account).status_code == 201

    second = _register(account, phone=None, full_name="Nguoi Thu Hai")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EMAIL_EXISTS"


def test_register_rejects_duplicate_phone(account) -> None:
    assert _register(account).status_code == 201

    second = _register(account, email=f"other.{uuid.uuid4().hex[:8]}@example.com")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "PHONE_EXISTS"


def test_register_does_not_create_user_when_email_duplicates(account, db) -> None:
    _register(account)
    _register(account, phone=None, full_name="Khong Duoc Tao")

    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM users WHERE email = %s", (account["email"],))
        assert cursor.fetchone()[0] == 1


@pytest.mark.parametrize("field,value", [("password", "1234567"), ("full_name", "")])
def test_register_validates_input(account, field, value) -> None:
    response = _register(account, **{field: value})
    assert response.status_code == 422


def test_register_validates_email(account) -> None:
    assert _register(account, email="khong-co-a-cong").status_code == 422


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------


def test_login_succeeds_with_correct_password(account) -> None:
    created = _register(account).json()

    response = client.post(
        LOGIN_URL, json={"email": account["email"], "password": account["password"]}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["user"]["id"] == created["user"]["id"]
    assert body["user"]["full_name"] == "Pytest User"
    assert body["access_token"]


def test_login_is_case_insensitive_on_email(account) -> None:
    _register(account)
    response = client.post(
        LOGIN_URL, json={"email": account["email"].upper(), "password": account["password"]}
    )
    assert response.status_code == 200


def test_login_updates_last_login_at(account, db) -> None:
    _register(account)
    with db.cursor() as cursor:
        cursor.execute("SELECT last_login_at FROM users WHERE email = %s", (account["email"],))
        assert cursor.fetchone()[0] is None

    client.post(LOGIN_URL, json={"email": account["email"], "password": account["password"]})

    with db.cursor() as cursor:
        cursor.execute("SELECT last_login_at FROM users WHERE email = %s", (account["email"],))
        assert cursor.fetchone()[0] is not None, "procedure phải COMMIT last_login_at"


def test_login_rejects_wrong_password(account, db) -> None:
    _register(account)
    response = client.post(LOGIN_URL, json={"email": account["email"], "password": "sai-mat-khau"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"

    with db.cursor() as cursor:
        cursor.execute("SELECT failed_login_count FROM users WHERE email = %s", (account["email"],))
        assert cursor.fetchone()[0] == 1


def test_login_rejects_unknown_email() -> None:
    unknown = f"khong.ton.tai.{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(LOGIN_URL, json={"email": unknown, "password": PASSWORD})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_locks_account_after_too_many_failures(account, db) -> None:
    _register(account)

    for _ in range(settings.login_max_failed_attempts):
        client.post(LOGIN_URL, json={"email": account["email"], "password": "sai-mat-khau"})

    locked = client.post(
        LOGIN_URL, json={"email": account["email"], "password": account["password"]}
    )
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert locked.json()["error"]["details"]["retry_after_seconds"] > 0


def test_login_rejects_suspended_account(account, db) -> None:
    _register(account)
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET status = 'SUSPENDED' WHERE email = %s", (account["email"],)
        )

    response = client.post(
        LOGIN_URL, json={"email": account["email"], "password": account["password"]}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_login_resets_failed_counter_on_success(account, db) -> None:
    _register(account)
    client.post(LOGIN_URL, json={"email": account["email"], "password": "sai-mat-khau"})
    client.post(LOGIN_URL, json={"email": account["email"], "password": account["password"]})

    with db.cursor() as cursor:
        cursor.execute("SELECT failed_login_count FROM users WHERE email = %s", (account["email"],))
        assert cursor.fetchone()[0] == 0
