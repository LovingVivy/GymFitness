"""Shared pytest fixtures.

The integration tests talk to the real MySQL instance because every statement
lives in a stored procedure — mocking the database would test nothing. Each
test creates its own account and removes everything the flow touched, so the
suite is repeatable on a shared development database.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from email.message import EmailMessage
from typing import Any

# Đặt trước khi import app: cấu hình được đọc một lần khi khởi tạo.
# Rate limit và cache tắt để các test độc lập với nhau (có test riêng bật chúng lên);
# tác vụ nền chạy đồng bộ để test kiểm tra được kết quả ngay sau request.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("JOB_QUEUE_MODE", "inline")
# Bảo trì định kỳ chỉ chạy khi test gọi trực tiếp maintenance.run_once().
os.environ.setdefault("MAINTENANCE_IN_API", "false")

import pymysql  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import mailer, storage  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

settings = get_settings()

client = TestClient(app)


def connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        autocommit=True,
    )


@pytest.fixture(scope="session")
def db() -> Iterator[pymysql.connections.Connection]:
    try:
        connection = connect()
    except pymysql.MySQLError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"MySQL không khả dụng: {exc}")
    yield connection
    connection.close()


def _fetch_one(cursor, sql: str, params: tuple[Any, ...]) -> Any:
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return row[0] if row else None


def purge_account(db: pymysql.connections.Connection, email: str) -> None:
    """Delete every row a register/subscribe/avatar/PT flow may have created.

    Deletion order follows the foreign keys: rows referencing a booking, a
    subscription or a wallet must go first.
    """
    with db.cursor() as cursor:
        user_id = _fetch_one(cursor, "SELECT id FROM users WHERE email = %s", (email,))
    if user_id is not None:
        purge_user(db, user_id)


def purge_user(db: pymysql.connections.Connection, user_id: str) -> None:
    """Same as :func:`purge_account` but by id (deleted accounts get anonymised emails)."""
    storage_keys: list[str] = []
    with db.cursor() as cursor:
        member_id = _fetch_one(cursor, "SELECT id FROM members WHERE user_id = %s", (user_id,))
        trainer_id = _fetch_one(
            cursor, "SELECT id FROM trainer_profiles WHERE user_id = %s", (user_id,)
        )

        if trainer_id is not None:
            cursor.execute("DELETE FROM trainer_availability WHERE trainer_id = %s", (trainer_id,))

        if member_id is not None:
            cursor.execute("DELETE FROM check_ins WHERE member_id = %s", (member_id,))
            cursor.execute(
                "DELETE FROM pt_credit_ledger WHERE credit_account_id IN "
                "(SELECT id FROM pt_credit_accounts WHERE member_id = %s)",
                (member_id,),
            )
            cursor.execute("DELETE FROM pt_bookings WHERE member_id = %s", (member_id,))
            cursor.execute(
                "DELETE FROM pt_credit_purchases WHERE credit_account_id IN "
                "(SELECT id FROM pt_credit_accounts WHERE member_id = %s)",
                (member_id,),
            )
            cursor.execute("DELETE FROM pt_credit_accounts WHERE member_id = %s", (member_id,))

            cursor.execute(
                "SELECT id FROM membership_subscriptions WHERE member_id = %s", (member_id,)
            )
            subscription_ids = [row[0] for row in cursor.fetchall()]
            for subscription_id in subscription_ids:
                cursor.execute(
                    "DELETE FROM subscription_status_history WHERE subscription_id = %s",
                    (subscription_id,),
                )
            cursor.execute(
                "DELETE FROM membership_subscriptions WHERE member_id = %s", (member_id,)
            )
            cursor.execute(
                "DELETE FROM payment_events WHERE payment_id IN "
                "(SELECT id FROM payments WHERE member_id = %s)",
                (member_id,),
            )
            cursor.execute(
                "DELETE FROM invoices WHERE payment_id IN "
                "(SELECT id FROM payments WHERE member_id = %s)",
                (member_id,),
            )
            cursor.execute("DELETE FROM payments WHERE member_id = %s", (member_id,))

        cursor.execute("SELECT storage_key FROM file_assets WHERE owner_user_id = %s", (user_id,))
        storage_keys = [row[0] for row in cursor.fetchall()]

        cursor.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM background_jobs WHERE requested_by = %s", (user_id,))
        cursor.execute("DELETE FROM audit_logs WHERE entity_id = %s", (user_id,))
        cursor.execute(
            "UPDATE user_profiles SET avatar_file_id = NULL WHERE user_id = %s", (user_id,)
        )
        cursor.execute("DELETE FROM file_assets WHERE owner_user_id = %s", (user_id,))

        if trainer_id is not None:
            cursor.execute("DELETE FROM trainer_specialties WHERE trainer_id = %s", (trainer_id,))
            cursor.execute("DELETE FROM trainer_profiles WHERE id = %s", (trainer_id,))

        cursor.execute("DELETE FROM members WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM user_profiles WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

    for storage_key in storage_keys:
        try:
            path = storage.storage_root() / storage_key
            if path.is_file():
                path.unlink()
        except (OSError, ValueError):  # pragma: no cover - best effort cleanup
            pass


@pytest.fixture
def purge(db: pymysql.connections.Connection):
    """Callable that removes every row created for an email address."""

    def _purge(email: str) -> None:
        purge_account(db, email)

    return _purge


@pytest.fixture
def account(db: pymysql.connections.Connection) -> Iterator[dict[str, str]]:
    """A unique account per test, fully removed afterwards."""
    email = f"pytest.{uuid.uuid4().hex[:12]}@example.com"
    phone = f"09{uuid.uuid4().int % 100_000_000:08d}"
    record = {"email": email, "phone": phone, "password": "password123"}
    yield record
    purge_account(db, email)


@pytest.fixture
def session(account: dict[str, str]) -> dict[str, Any]:
    """A registered account plus its bearer token."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Pytest User",
            "email": account["email"],
            "phone": account["phone"],
            "password": account["password"],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "account": account,
        "token": body["access_token"],
        "user": body["user"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }


@pytest.fixture(autouse=True)
def outbox(monkeypatch) -> list[EmailMessage]:
    """Every email the code tries to send during a test, instead of SMTP or disk."""
    sent: list[EmailMessage] = []

    def capture(message: EmailMessage) -> str:
        sent.append(message)
        return "test-outbox"

    monkeypatch.setattr(mailer, "deliver", capture)
    return sent


def mail_text(message: EmailMessage) -> str:
    """Plain-text body of a captured email."""
    part = message.get_body(preferencelist=("plain",))
    return part.get_content() if part else ""
