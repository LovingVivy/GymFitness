"""Membership lifecycle: early renewal, expiry, renewal reminders and staff audit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.tasks import maintenance
from tests.conftest import client, mail_text

PROFILE_URL = "/api/v1/profile"
NOTIFICATIONS_URL = "/api/v1/notifications"


def _plan_id(code: str) -> str:
    return next(item["id"] for item in client.get("/api/v1/plans").json() if item["code"] == code)


def _buy(session: dict, code: str, pay: bool = True) -> dict:
    created = client.post(
        "/api/v1/subscriptions", json={"plan_id": _plan_id(code)}, headers=session["headers"]
    )
    assert created.status_code == 201, created.text
    payment = created.json()["payment"]
    if pay:
        paid = client.post(
            f"/api/v1/payments/{payment['id']}/mark-paid", headers=session["headers"]
        )
        assert paid.status_code == 200, paid.text
    return created.json()


def _subscriptions(db, user_id: str) -> list[tuple]:
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT s.id, s.status, s.start_at, s.end_at FROM membership_subscriptions s "
            "JOIN members m ON m.id = s.member_id WHERE m.user_id = %s ORDER BY s.start_at",
            (user_id,),
        )
        return list(cursor.fetchall())


def _move_end(db, subscription_id: str, end_in: timedelta) -> None:
    """Dời ngày hết hạn trực tiếp trong DB để thử các mốc thời gian."""
    end = (datetime.now(UTC) + end_in).replace(tzinfo=None)
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE membership_subscriptions SET start_at = %s - INTERVAL 1 MONTH, end_at = %s "
            "WHERE id = %s",
            (end, end, subscription_id),
        )


def _notes(session: dict, kind: str) -> list[dict]:
    items = client.get(NOTIFICATIONS_URL, headers=session["headers"]).json()["items"]
    return [item for item in items if item["notification_type"] == kind]


def test_early_renewal_continues_after_the_current_plan(session, db) -> None:
    _buy(session, "GYM_MONTHLY")
    _buy(session, "GYM_MONTHLY")
    first, second = _subscriptions(db, session["user"]["id"])
    assert second[2] == first[3], "gói mới bắt đầu đúng lúc gói cũ hết hạn"
    assert second[3] > first[3]

    profile = client.get(PROFILE_URL, headers=session["headers"]).json()
    assert profile["membership"]["subscription_id"] == second[0]
    # Còn khoảng 2 tháng; tổng thời hạn tính cả chuỗi gói.
    assert 55 <= profile["membership"]["days_remaining"] <= 63
    assert profile["membership"]["total_days"] >= profile["membership"]["days_remaining"]
    assert [item["activity_type"] for item in profile["memberships"]] == ["GYM"]


def test_a_second_activity_is_a_separate_plan(session) -> None:
    _buy(session, "GYM_MONTHLY")
    _buy(session, "YOGA_YEARLY")
    profile = client.get(PROFILE_URL, headers=session["headers"]).json()
    assert {item["activity_type"] for item in profile["memberships"]} == {"GYM", "YOGA"}
    yoga = next(item for item in profile["memberships"] if item["activity_type"] == "YOGA")
    assert yoga["days_remaining"] >= 360


def test_expired_plan_shows_expired_and_is_closed_by_maintenance(session, db, outbox) -> None:
    created = _buy(session, "GYM_MONTHLY")
    _move_end(db, created["subscription_id"], timedelta(hours=-1))

    # Tác vụ định kỳ chưa chạy: hồ sơ vẫn báo đúng là đã hết hạn.
    profile = client.get(PROFILE_URL, headers=session["headers"]).json()
    assert profile["membership"]["status"] == "EXPIRED"
    assert profile["membership"]["days_remaining"] == 0
    assert profile["memberships"] == []

    assert maintenance.run_once().expired >= 1
    assert [row[1] for row in _subscriptions(db, session["user"]["id"])] == ["EXPIRED"]
    assert len(_notes(session, "MEMBERSHIP_EXPIRED")) == 1
    emails = [mail for mail in outbox if mail["To"] == session["account"]["email"]]
    assert any("đã hết hạn" in mail["Subject"] for mail in emails)

    # Chạy lại không tạo thông báo trùng.
    maintenance.run_once()
    assert len(_notes(session, "MEMBERSHIP_EXPIRED")) == 1


@pytest.mark.parametrize(
    ("end_in", "days_left"),
    [(timedelta(days=6), 7), (timedelta(hours=50), 3), (timedelta(hours=5), 1)],
)
def test_renewal_reminders_are_sent_once_per_step(session, db, outbox, end_in, days_left) -> None:
    created = _buy(session, "GYM_MONTHLY")
    _move_end(db, created["subscription_id"], end_in)

    maintenance.run_once()
    maintenance.run_once()
    reminders = _notes(session, "MEMBERSHIP_EXPIRING")
    assert len(reminders) == 1
    assert reminders[0]["data"]["days_left"] == days_left
    assert reminders[0]["action_url"] == "/plans"

    emails = [mail for mail in outbox if "sắp hết hạn" in mail["Subject"]]
    assert [mail["To"] for mail in emails] == [session["account"]["email"]]
    assert "/plans" in mail_text(emails[0])


def test_renewed_plan_gets_no_reminder(session, db) -> None:
    created = _buy(session, "GYM_MONTHLY")
    _move_end(db, created["subscription_id"], timedelta(days=2))
    _buy(session, "GYM_MONTHLY")

    maintenance.run_once()
    assert _notes(session, "MEMBERSHIP_EXPIRING") == []


def test_staff_confirmation_through_mark_paid_is_audited(session, db) -> None:
    created = _buy(session, "GYM_MONTHLY", pay=False)
    # Nhân viên dùng chung endpoint mark-paid: vẫn phải có dấu vết trong nhật ký.
    with db.cursor() as cursor:
        cursor.execute("UPDATE users SET role = 'MANAGER' WHERE id = %s", (session["user"]["id"],))
    paid = client.post(
        f"/api/v1/payments/{created['payment']['id']}/mark-paid", headers=session["headers"]
    )
    assert paid.status_code == 200, paid.text
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT actor_user_id FROM audit_logs WHERE action = 'PAYMENT_CONFIRM' "
            "AND entity_id = %s",
            (created["payment"]["id"],),
        )
        rows = cursor.fetchall()
        cursor.execute(
            "DELETE FROM audit_logs WHERE entity_type = 'payment' AND entity_id = %s",
            (created["payment"]["id"],),
        )
    assert [row[0] for row in rows] == [session["user"]["id"]]
