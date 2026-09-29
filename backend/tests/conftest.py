"""Shared pytest fixtures.

The integration tests talk to the real MySQL instance because every statement
lives in a stored procedure — mocking the database would test nothing. Each
test creates its own account and removes everything the flow touched, so the
suite is repeatable on a shared development database.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pymysql
import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.config import get_settings
from app.main import app

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
        if user_id is None:
            return

        member_id = _fetch_one(cursor, "SELECT id FROM members WHERE user_id = %s", (user_id,))
        trainer_id = _fetch_one(
            cursor, "SELECT id FROM trainer_profiles WHERE user_id = %s", (user_id,)
        )

        if trainer_id is not None:
            cursor.execute("DELETE FROM trainer_availability WHERE trainer_id = %s", (trainer_id,))

        if member_id is not None:
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
            cursor.execute("DELETE FROM payments WHERE member_id = %s", (member_id,))

        cursor.execute("SELECT storage_key FROM file_assets WHERE owner_user_id = %s", (user_id,))
        storage_keys = [row[0] for row in cursor.fetchall()]

        cursor.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
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
