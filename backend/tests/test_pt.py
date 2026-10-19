"""Integration tests for trainer schedules, PT sessions, credits and notifications.

Two trainer accounts (one Gym, one Yoga) are created through the admin API
for this module and removed afterwards, so the suite does not depend on seed
data an admin may have deleted. Member accounts are created per test and fully
removed by the shared fixtures. Cleanup only touches rows of these trainers and
members, leaving real schedules and bookings on the dev database alone.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import client, mail_text, purge_user

TRAINERS_URL = "/api/v1/trainers"
SCHEDULE_URL = f"{TRAINERS_URL}/me/schedule"
TIME_OFF_URL = f"{TRAINERS_URL}/me/time-off"
CREDITS_URL = "/api/v1/pt-credits"
BOOKINGS_URL = "/api/v1/pt-bookings"
TEACHING_URL = f"{BOOKINGS_URL}/teaching"
NOTIFICATIONS_URL = "/api/v1/notifications"
SUBSCRIPTIONS_URL = "/api/v1/subscriptions"

PT_PASSWORD = f"pt-{uuid.uuid4().hex[:12]}"

# Filled by ``trainer_accounts``: {"GYM": {"id", "user_id", "email"}, "YOGA": {...}}.
TRAINERS: dict[str, dict[str, str]] = {}

_TRAINER_SPECIALTIES = {"GYM": ["GYM", "MUSCLE_GAIN"], "YOGA": ["YOGA", "FLEXIBILITY"]}


def trainer_ids() -> tuple[str, str]:
    return (TRAINERS["GYM"]["id"], TRAINERS["YOGA"]["id"])


@pytest.fixture(scope="module", autouse=True)
def trainer_accounts(db) -> Iterator[dict[str, dict[str, str]]]:
    """Create a Gym and a Yoga trainer the way an admin would, then remove them."""
    tag = uuid.uuid4().hex[:8]
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Pytest PT Admin",
            "email": f"pytest.ptadmin.{tag}@example.com",
            "password": "password123",
        },
    )
    assert registered.status_code == 201, registered.text
    admin_id = registered.json()["user"]["id"]
    with db.cursor() as cursor:
        cursor.execute("UPDATE users SET role = 'ADMIN' WHERE id = %s", (admin_id,))
    admin_headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    try:
        for activity, specialties in _TRAINER_SPECIALTIES.items():
            email = f"pytest.pt.{activity.lower()}.{tag}@example.com"
            created = client.post(
                "/api/v1/admin/users",
                json={
                    "full_name": f"Pytest PT {activity.title()}",
                    "email": email,
                    "password": PT_PASSWORD,
                    "role": "PT",
                    "specialties": specialties,
                },
                headers=admin_headers,
            )
            assert created.status_code == 201, created.text
            profile = client.get(f"{TRAINERS_URL}/me", headers=_login(email, PT_PASSWORD)).json()
            TRAINERS[activity] = {
                "id": profile["id"],
                "user_id": created.json()["id"],
                "email": email,
            }
        yield TRAINERS
    finally:
        with db.cursor() as cursor:
            for trainer in TRAINERS.values():
                cursor.execute(
                    "DELETE FROM trainer_weekly_schedule WHERE trainer_id = %s", (trainer["id"],)
                )
                cursor.execute(
                    "DELETE FROM trainer_time_off WHERE trainer_id = %s", (trainer["id"],)
                )
        for trainer in TRAINERS.values():
            purge_user(db, trainer["user_id"])
        purge_user(db, admin_id)
        TRAINERS.clear()


EVERY_DAY = [{"weekday": day, "start_time": "06:00", "end_time": "22:00"} for day in range(1, 8)]


@pytest.fixture(autouse=True)
def reset_pt_state(db, trainer_accounts) -> Iterator[None]:
    """Snapshot schedules, then clean bookings/notifications after each test.

    Declared autouse so it tears down *last*, after ``purge_account`` has
    removed the rows that reference these bookings.
    """
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT id, trainer_id, weekday, start_time, end_time FROM trainer_weekly_schedule"
            " WHERE trainer_id IN (%s, %s)",
            trainer_ids(),
        )
        schedule = cursor.fetchall()
        cursor.execute(
            "SELECT id, trainer_id, start_at, end_at, reason, deleted_at FROM trainer_time_off"
            " WHERE trainer_id IN (%s, %s)",
            trainer_ids(),
        )
        time_off = cursor.fetchall()
        # Mỗi test bắt đầu với hai PT của module chưa có lịch.
        cursor.execute(
            "DELETE FROM trainer_weekly_schedule WHERE trainer_id IN (%s, %s)", trainer_ids()
        )
        cursor.execute("DELETE FROM trainer_time_off WHERE trainer_id IN (%s, %s)", trainer_ids())

    yield

    with db.cursor() as cursor:
        cursor.execute(
            "DELETE FROM pt_credit_ledger WHERE booking_id IN "
            "(SELECT id FROM pt_bookings WHERE trainer_id IN (%s, %s))",
            trainer_ids(),
        )
        cursor.execute("DELETE FROM pt_bookings WHERE trainer_id IN (%s, %s)", trainer_ids())
        cursor.execute(
            "DELETE FROM notifications WHERE user_id IN "
            "(SELECT id FROM users WHERE email IN (%s, %s))",
            (TRAINERS["GYM"]["email"], TRAINERS["YOGA"]["email"]),
        )
        cursor.execute(
            "DELETE FROM trainer_weekly_schedule WHERE trainer_id IN (%s, %s)", trainer_ids()
        )
        cursor.execute("DELETE FROM trainer_time_off WHERE trainer_id IN (%s, %s)", trainer_ids())
        if schedule:
            cursor.executemany(
                "INSERT INTO trainer_weekly_schedule"
                " (id, trainer_id, weekday, start_time, end_time) VALUES (%s, %s, %s, %s, %s)",
                schedule,
            )
        if time_off:
            cursor.executemany(
                "INSERT INTO trainer_time_off"
                " (id, trainer_id, start_at, end_at, reason, deleted_at)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                time_off,
            )


def _login(email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def gym_trainer() -> dict[str, str]:
    return _login(TRAINERS["GYM"]["email"], PT_PASSWORD)


@pytest.fixture
def yoga_trainer() -> dict[str, str]:
    return _login(TRAINERS["YOGA"]["email"], PT_PASSWORD)


def _set_schedule(headers: dict[str, str], weekly: list[dict] | None = None) -> dict:
    response = client.put(SCHEDULE_URL, json={"weekly": weekly or EVERY_DAY}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _slots(headers: dict[str, str], trainer_id: str | None = None) -> list[dict]:
    trainer_id = trainer_id or TRAINERS["GYM"]["id"]
    response = client.get(f"{TRAINERS_URL}/{trainer_id}/slots", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _subscribe(session: dict, plan_code: str = "GYM_YEARLY") -> None:
    plans = client.get("/api/v1/plans").json()
    plan = next(item for item in plans if item["code"] == plan_code)
    created = client.post(
        SUBSCRIPTIONS_URL, json={"plan_id": plan["id"]}, headers=session["headers"]
    )
    assert created.status_code == 201, created.text
    paid = client.post(
        f"/api/v1/payments/{created.json()['payment']['id']}/mark-paid",
        headers=session["headers"],
    )
    assert paid.status_code == 200, paid.text


def _buy_credits(session: dict, quantity: int = 3) -> None:
    created = client.post(
        f"{CREDITS_URL}/purchase", json={"quantity": quantity}, headers=session["headers"]
    )
    assert created.status_code == 201, created.text
    paid = client.post(
        f"/api/v1/payments/{created.json()['payment_id']}/mark-paid",
        headers=session["headers"],
    )
    assert paid.status_code == 200, paid.text


def _ready_member(session: dict, credits: int = 3) -> None:
    _subscribe(session)
    _buy_credits(session, credits)


def _book(session: dict, start_at: str, trainer_id: str | None = None):
    trainer_id = trainer_id or TRAINERS["GYM"]["id"]
    return client.post(
        BOOKINGS_URL,
        json={"trainer_id": trainer_id, "start_at": start_at, "notes": "Buổi tập đầu tiên"},
        headers=session["headers"],
    )


def _booked(session: dict, gym_trainer: dict[str, str], credits: int = 3) -> dict:
    _set_schedule(gym_trainer)
    _ready_member(session, credits)
    slot = _slots(session["headers"])[0]
    response = _book(session, slot["start_at"])
    assert response.status_code == 201, response.text
    return response.json()


def _wallet(session: dict) -> dict:
    return client.get(CREDITS_URL, headers=session["headers"]).json()


def _move_booking(db, booking_id: str, starts_in: timedelta) -> None:
    """Dời giờ buổi tập trực tiếp trong DB để thử các mốc thời gian."""
    start = (datetime.now(UTC) + starts_in).replace(tzinfo=None)
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE pt_bookings SET start_at = %s, end_at = %s WHERE id = %s",
            (start, start + timedelta(hours=1), booking_id),
        )


@pytest.fixture
def second_member(purge) -> Iterator[dict]:
    email = f"pytest.second.{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Second Member",
            "email": email,
            "phone": f"09{uuid.uuid4().int % 100_000_000:08d}",
            "password": "password123",
        },
    )
    assert response.status_code == 201, response.text
    yield {"headers": {"Authorization": f"Bearer {response.json()['access_token']}"}}
    purge(email)


# --------------------------------------------------------------------------
# Trainer accounts created by an admin
# --------------------------------------------------------------------------


@pytest.mark.parametrize("activity", ["GYM", "YOGA"])
def test_admin_created_trainer_can_log_in(activity) -> None:
    headers = _login(TRAINERS[activity]["email"], PT_PASSWORD)
    profile = client.get(f"{TRAINERS_URL}/me", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["employee_code"].startswith("PT")
    assert set(body["specialties"]) == set(_TRAINER_SPECIALTIES[activity])
    assert body["hourly_rate"] > 0


def test_member_cannot_use_trainer_endpoints(session) -> None:
    headers = session["headers"]
    assert client.get(f"{TRAINERS_URL}/me", headers=headers).status_code == 403
    assert client.get(SCHEDULE_URL, headers=headers).status_code == 403
    assert client.put(SCHEDULE_URL, json={"weekly": EVERY_DAY}, headers=headers).status_code == 403
    assert client.get(TEACHING_URL, headers=headers).status_code == 403


def test_trainer_endpoints_require_token() -> None:
    assert client.get(f"{TRAINERS_URL}/me").status_code == 401
    assert client.get(SCHEDULE_URL).status_code == 401


# --------------------------------------------------------------------------
# "Lịch của bạn": weekly schedule and time off
# --------------------------------------------------------------------------


def test_trainer_without_schedule_is_hidden_from_members(session, gym_trainer) -> None:
    body = client.get(SCHEDULE_URL, headers=gym_trainer).json()
    assert body["weekly"] == []
    assert body["session_minutes"] == 60
    assert body["timezone"] == "GMT+7"

    catalogue = client.get(TRAINERS_URL, headers=session["headers"]).json()
    assert TRAINERS["GYM"]["id"] not in {trainer["id"] for trainer in catalogue}


def test_trainer_saves_weekly_schedule(session, gym_trainer) -> None:
    body = _set_schedule(
        gym_trainer,
        [
            {"weekday": 3, "start_time": "17:00", "end_time": "21:00"},
            {"weekday": 1, "start_time": "06:00", "end_time": "08:00"},
            {"weekday": 1, "start_time": "17:00", "end_time": "20:00"},
        ],
    )
    assert [(item["weekday"], item["start_time"]) for item in body["weekly"]] == [
        (1, "06:00"),
        (1, "17:00"),
        (3, "17:00"),
    ]

    trainer = next(
        item
        for item in client.get(TRAINERS_URL, headers=session["headers"]).json()
        if item["id"] == TRAINERS["GYM"]["id"]
    )
    assert trainer["schedule_weekdays"] == [1, 3]


def test_saving_replaces_previous_schedule(gym_trainer) -> None:
    _set_schedule(gym_trainer)
    body = _set_schedule(gym_trainer, [{"weekday": 7, "start_time": "08:00", "end_time": "10:00"}])
    assert body["weekly"] == [{"weekday": 7, "start_time": "08:00", "end_time": "10:00"}]


@pytest.mark.parametrize(
    ("weekly", "code"),
    [
        (
            [
                {"weekday": 2, "start_time": "17:00", "end_time": "20:00"},
                {"weekday": 2, "start_time": "19:00", "end_time": "21:00"},
            ],
            "VALIDATION_ERROR",
        ),
        ([{"weekday": 2, "start_time": "17:00", "end_time": "17:30"}], "SCHEDULE_TOO_SHORT"),
        ([{"weekday": 2, "start_time": "7h", "end_time": "9h"}], "VALIDATION_ERROR"),
        ([{"weekday": 8, "start_time": "07:00", "end_time": "09:00"}], "VALIDATION_ERROR"),
        ([{"weekday": 2, "start_time": "20:00", "end_time": "18:00"}], "VALIDATION_ERROR"),
    ],
)
def test_invalid_schedules_are_rejected(gym_trainer, weekly, code) -> None:
    response = client.put(SCHEDULE_URL, json={"weekly": weekly}, headers=gym_trainer)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_slots_follow_schedule_and_session_length(session, gym_trainer) -> None:
    _set_schedule(
        gym_trainer,
        [{"weekday": day, "start_time": "17:00", "end_time": "20:00"} for day in range(1, 8)],
    )
    slots = _slots(session["headers"])

    assert slots, "lịch cả tuần phải sinh ra ô trống"
    assert {slot["local_start"] for slot in slots} <= {"17:00", "18:00", "19:00"}
    for slot in slots:
        start = datetime.fromisoformat(slot["start_at"])
        end = datetime.fromisoformat(slot["end_at"])
        assert end - start == timedelta(hours=1)
        assert start >= datetime.now(UTC) + timedelta(minutes=119)
        assert start <= datetime.now(UTC) + timedelta(days=14, minutes=1)
        # 17:00 giờ Việt Nam = 10:00 UTC.
        assert (start.hour, slot["local_start"]) in {(10, "17:00"), (11, "18:00"), (12, "19:00")}


def test_time_off_removes_slots(session, gym_trainer) -> None:
    _set_schedule(gym_trainer)
    first = _slots(session["headers"])[0]

    response = client.post(
        TIME_OFF_URL,
        json={"start_at": first["start_at"], "end_at": first["end_at"], "reason": "Khám sức khoẻ"},
        headers=gym_trainer,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["time_off"]) == 1
    assert body["time_off"][0]["reason"] == "Khám sức khoẻ"

    starts = {slot["start_at"] for slot in _slots(session["headers"])}
    assert first["start_at"] not in starts

    removed = client.delete(f"{TIME_OFF_URL}/{body['time_off'][0]['id']}", headers=gym_trainer)
    assert removed.status_code == 200
    assert first["start_at"] in {slot["start_at"] for slot in _slots(session["headers"])}


def test_time_off_in_the_past_is_rejected(gym_trainer) -> None:
    start = datetime.now(UTC) - timedelta(days=2)
    response = client.post(
        TIME_OFF_URL,
        json={"start_at": start.isoformat(), "end_at": (start + timedelta(hours=2)).isoformat()},
        headers=gym_trainer,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PAST_WINDOW"


def test_other_trainer_cannot_delete_time_off(gym_trainer, yoga_trainer) -> None:
    start = datetime.now(UTC) + timedelta(days=3)
    body = client.post(
        TIME_OFF_URL,
        json={"start_at": start.isoformat(), "end_at": (start + timedelta(hours=2)).isoformat()},
        headers=gym_trainer,
    ).json()
    response = client.delete(f"{TIME_OFF_URL}/{body['time_off'][0]['id']}", headers=yoga_trainer)
    assert response.status_code == 404


# --------------------------------------------------------------------------
# PT credits
# --------------------------------------------------------------------------


def test_pt_credit_starts_empty(session) -> None:
    body = _wallet(session)
    assert body["purchased"] == 0
    assert body["available"] == 0


def test_buying_credits_needs_payment_confirmation(session) -> None:
    created = client.post(
        f"{CREDITS_URL}/purchase", json={"quantity": 4}, headers=session["headers"]
    )
    assert created.status_code == 201
    assert created.json()["status"] == "PENDING"
    assert _wallet(session)["purchased"] == 0, "chưa xác nhận thanh toán thì chưa cộng lượt"

    paid = client.post(
        f"/api/v1/payments/{created.json()['payment_id']}/mark-paid",
        headers=session["headers"],
    )
    assert paid.status_code == 200

    after = _wallet(session)
    assert after["purchased"] == 4
    assert after["available"] == 4


def test_credit_purchase_requires_quantity(session) -> None:
    response = client.post(
        f"{CREDITS_URL}/purchase", json={"quantity": 0}, headers=session["headers"]
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Booking: confirmed immediately
# --------------------------------------------------------------------------


def test_booking_requires_active_subscription(session, gym_trainer) -> None:
    _set_schedule(gym_trainer)
    _buy_credits(session, 2)
    response = _book(session, _slots(session["headers"])[0]["start_at"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_ACTIVE_SUBSCRIPTION"


def _bookable_ids(session: dict) -> set[str]:
    response = client.get(f"{TRAINERS_URL}/bookable", headers=session["headers"])
    assert response.status_code == 200, response.text
    return {trainer["id"] for trainer in response.json()}


def test_bookable_trainers_follow_the_members_plan(session, gym_trainer, yoga_trainer) -> None:
    _set_schedule(gym_trainer)
    _set_schedule(yoga_trainer)

    # Chưa có gói: không đặt được ai.
    assert _bookable_ids(session) & set(trainer_ids()) == set()

    _subscribe(session, "GYM_YEARLY")
    assert _bookable_ids(session) & set(trainer_ids()) == {TRAINERS["GYM"]["id"]}

    # Mua thêm gói Yoga thì đặt được cả PT Yoga.
    _subscribe(session, "YOGA_MONTHLY")
    assert _bookable_ids(session) & set(trainer_ids()) == set(trainer_ids())


def test_bookable_trainers_need_a_schedule_and_a_token(session, gym_trainer) -> None:
    _subscribe(session, "GYM_YEARLY")
    assert TRAINERS["GYM"]["id"] not in _bookable_ids(session)
    assert client.get(f"{TRAINERS_URL}/bookable").status_code == 401


def test_gym_member_cannot_book_yoga_trainer(session, yoga_trainer) -> None:
    _set_schedule(yoga_trainer)
    _ready_member(session)  # gói GYM_YEARLY + lượt PT
    slot = _slots(session["headers"], TRAINERS["YOGA"]["id"])[0]

    response = _book(session, slot["start_at"], trainer_id=TRAINERS["YOGA"]["id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRAINER_MISMATCH"
    assert _wallet(session)["reserved"] == 0, "không được giữ lượt khi đặt sai loại hình"


def test_yoga_member_books_yoga_trainer(session, yoga_trainer) -> None:
    _set_schedule(yoga_trainer)
    _subscribe(session, "YOGA_YEARLY")
    _buy_credits(session, 1)
    slot = _slots(session["headers"], TRAINERS["YOGA"]["id"])[0]

    response = _book(session, slot["start_at"], trainer_id=TRAINERS["YOGA"]["id"])
    assert response.status_code == 201, response.text
    assert response.json()["activity_type"] == "YOGA"


def test_booking_requires_credits(session, gym_trainer) -> None:
    _set_schedule(gym_trainer)
    _subscribe(session)
    response = _book(session, _slots(session["headers"])[0]["start_at"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_PT_CREDIT"


def test_booking_is_confirmed_and_notifies_trainer(session, gym_trainer) -> None:
    booking = _booked(session, gym_trainer)

    assert booking["status"] == "ACCEPTED", "đặt là xác nhận ngay, không chờ PT duyệt"
    assert booking["trainer_name"]
    assert booking["notes"] == "Buổi tập đầu tiên"
    assert booking["local_label"]
    assert booking["refund_deadline"]

    wallet = _wallet(session)
    assert wallet["reserved"] == 1
    assert wallet["available"] == 2

    teaching = client.get(TEACHING_URL, headers=gym_trainer).json()
    assert [item["id"] for item in teaching] == [booking["id"]]
    assert teaching[0]["member_name"] == "Pytest User"

    notifications = client.get(NOTIFICATIONS_URL, headers=gym_trainer).json()
    booked = [n for n in notifications["items"] if n["notification_type"] == "PT_SESSION_BOOKED"]
    assert booked and booked[0]["data"]["booking_id"] == booking["id"]
    assert booking["local_label"] in booked[0]["body"], "thông báo dùng giờ Việt Nam"


def test_booked_slot_disappears_and_cannot_be_taken_twice(
    session, second_member, gym_trainer
) -> None:
    booking = _booked(session, gym_trainer)
    assert booking["start_at"] not in {slot["start_at"] for slot in _slots(session["headers"])}

    _ready_member(second_member)
    response = _book(second_member, booking["start_at"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLOT_UNAVAILABLE"


def test_member_cannot_book_two_trainers_at_once(session, gym_trainer, yoga_trainer) -> None:
    booking = _booked(session, gym_trainer)
    _subscribe(session, "YOGA_YEARLY")
    _set_schedule(yoga_trainer)

    response = _book(session, booking["start_at"], trainer_id=TRAINERS["YOGA"]["id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MEMBER_BUSY"


def test_booking_must_start_on_a_slot_boundary(session, gym_trainer) -> None:
    _set_schedule(gym_trainer)
    _ready_member(session)
    start = datetime.fromisoformat(_slots(session["headers"])[0]["start_at"])

    response = _book(session, (start + timedelta(minutes=30)).isoformat())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OUTSIDE_SCHEDULE"


def test_booking_outside_working_days_is_rejected(session, gym_trainer) -> None:
    _set_schedule(gym_trainer, [{"weekday": 1, "start_time": "17:00", "end_time": "19:00"}])
    _ready_member(session)
    monday_slot = datetime.fromisoformat(_slots(session["headers"])[0]["start_at"])

    response = _book(session, (monday_slot + timedelta(days=1)).isoformat())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OUTSIDE_SCHEDULE"


def test_booking_too_soon_is_rejected(session, gym_trainer) -> None:
    _set_schedule(gym_trainer)
    _ready_member(session)
    response = _book(session, (datetime.now(UTC) + timedelta(minutes=30)).isoformat())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TOO_SOON"


def test_booking_during_time_off_is_rejected(session, gym_trainer) -> None:
    _set_schedule(gym_trainer)
    _ready_member(session)
    slot = _slots(session["headers"])[0]
    client.post(
        TIME_OFF_URL,
        json={"start_at": slot["start_at"], "end_at": slot["end_at"]},
        headers=gym_trainer,
    )

    response = _book(session, slot["start_at"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRAINER_OFF"


# --------------------------------------------------------------------------
# Cancelling
# --------------------------------------------------------------------------


def test_member_early_cancel_refunds_credit(session, gym_trainer, db, outbox) -> None:
    booking = _booked(session, gym_trainer)
    # Ô đầu tiên chỉ cách ~2 giờ (dưới mốc 12 giờ), dời ra xa để là huỷ sớm.
    _move_booking(db, booking["id"], timedelta(days=2))

    response = client.post(f"{BOOKINGS_URL}/{booking['id']}/cancel", headers=session["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["refunded"] is True
    assert body["booking"]["status"] == "CANCELLED"
    assert body["booking"]["cancelled_by_role"] == "MEMBER"

    wallet = _wallet(session)
    assert (wallet["reserved"], wallet["used"], wallet["available"]) == (0, 0, 3)

    notifications = client.get(NOTIFICATIONS_URL, headers=gym_trainer).json()["items"]
    assert any(n["notification_type"] == "PT_SESSION_CANCELLED" for n in notifications)

    # PT cũng nhận email qua hàng đợi tác vụ.
    emails = [mail for mail in outbox if mail["To"] == TRAINERS["GYM"]["email"]]
    assert len(emails) == 1
    assert "hội viên" in mail_text(emails[0])


def test_member_late_cancel_consumes_credit(session, gym_trainer, db) -> None:
    booking = _booked(session, gym_trainer)
    _move_booking(db, booking["id"], timedelta(hours=3))

    response = client.post(
        f"{BOOKINGS_URL}/{booking['id']}/cancel",
        json={"reason": "Bận đột xuất"},
        headers=session["headers"],
    )
    assert response.status_code == 200
    assert response.json()["refunded"] is False

    wallet = _wallet(session)
    assert (wallet["reserved"], wallet["used"], wallet["available"]) == (0, 1, 2)


def test_trainer_cancel_requires_reason_and_always_refunds(
    session, gym_trainer, db, outbox
) -> None:
    booking = _booked(session, gym_trainer)
    _move_booking(db, booking["id"], timedelta(hours=3))

    missing = client.post(f"{BOOKINGS_URL}/{booking['id']}/cancel", headers=gym_trainer)
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "REASON_REQUIRED"

    response = client.post(
        f"{BOOKINGS_URL}/{booking['id']}/cancel",
        json={"reason": "Ốm đột xuất"},
        headers=gym_trainer,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["refunded"] is True
    assert body["booking"]["cancelled_by_role"] == "TRAINER"
    assert body["booking"]["cancellation_reason"] == "Ốm đột xuất"
    assert _wallet(session)["available"] == 3

    member_notes = client.get(NOTIFICATIONS_URL, headers=session["headers"]).json()["items"]
    cancelled = [n for n in member_notes if n["notification_type"] == "PT_SESSION_CANCELLED"]
    assert cancelled and "Ốm đột xuất" in cancelled[0]["body"]

    emails = [mail for mail in outbox if "đã bị huỷ" in mail["Subject"]]
    assert [mail["To"] for mail in emails] == [session["account"]["email"]]
    assert "Ốm đột xuất" in mail_text(emails[0])
    assert "hoàn lại" in mail_text(emails[0])


def test_strangers_cannot_cancel(session, second_member, gym_trainer, yoga_trainer) -> None:
    booking = _booked(session, gym_trainer)
    url = f"{BOOKINGS_URL}/{booking['id']}/cancel"
    assert client.post(url, headers=second_member["headers"]).status_code == 404
    assert client.post(url, json={"reason": "x"}, headers=yoga_trainer).status_code == 404


def test_cannot_cancel_started_session(session, gym_trainer, db) -> None:
    booking = _booked(session, gym_trainer)
    _move_booking(db, booking["id"], timedelta(minutes=-10))
    response = client.post(f"{BOOKINGS_URL}/{booking['id']}/cancel", headers=session["headers"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_STARTED"


# --------------------------------------------------------------------------
# Closing out a session
# --------------------------------------------------------------------------


def test_cannot_complete_before_start(session, gym_trainer) -> None:
    booking = _booked(session, gym_trainer)
    response = client.post(f"{BOOKINGS_URL}/{booking['id']}/complete", headers=gym_trainer)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_NOT_STARTED"


@pytest.mark.parametrize(("action", "final"), [("complete", "COMPLETED"), ("no-show", "NO_SHOW")])
def test_trainer_closes_session(session, gym_trainer, db, action, final) -> None:
    booking = _booked(session, gym_trainer)
    _move_booking(db, booking["id"], timedelta(minutes=-30))

    response = client.post(f"{BOOKINGS_URL}/{booking['id']}/{action}", headers=gym_trainer)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == final

    wallet = _wallet(session)
    assert (wallet["reserved"], wallet["used"], wallet["available"]) == (0, 1, 2)

    again = client.post(f"{BOOKINGS_URL}/{booking['id']}/{action}", headers=gym_trainer)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "BOOKING_NOT_ACTIVE"


def test_only_the_assigned_trainer_closes_session(session, gym_trainer, yoga_trainer, db) -> None:
    booking = _booked(session, gym_trainer)
    _move_booking(db, booking["id"], timedelta(minutes=-30))
    response = client.post(f"{BOOKINGS_URL}/{booking['id']}/complete", headers=yoga_trainer)
    assert response.status_code == 404


def test_member_cannot_close_sessions(session, gym_trainer) -> None:
    booking = _booked(session, gym_trainer)
    response = client.post(f"{BOOKINGS_URL}/{booking['id']}/complete", headers=session["headers"])
    assert response.status_code == 403


# --------------------------------------------------------------------------
# Schedule changes never silently drop booked sessions
# --------------------------------------------------------------------------


def test_schedule_change_reports_conflicting_sessions(session, gym_trainer) -> None:
    booking = _booked(session, gym_trainer)
    other_days = [item for item in EVERY_DAY if item["weekday"] != _local_weekday(booking)]
    body = _set_schedule(gym_trainer, other_days)

    assert [item["id"] for item in body["conflicts"]] == [booking["id"]]
    teaching = client.get(TEACHING_URL, headers=gym_trainer).json()
    assert teaching[0]["status"] == "ACCEPTED", "buổi đã đặt giữ nguyên, PT tự quyết định huỷ"


def _local_weekday(booking: dict) -> int:
    """Thứ trong tuần theo giờ Việt Nam (UTC+7) của buổi đã đặt."""
    start = datetime.fromisoformat(booking["start_at"])
    return (start + timedelta(hours=7)).isoweekday()


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------


def test_marking_notifications_read(session, gym_trainer, db) -> None:
    booking = _booked(session, gym_trainer)
    # Bỏ qua thông báo "thanh toán thành công" của bước chuẩn bị (gói + lượt PT).
    client.post(f"{NOTIFICATIONS_URL}/read-all", headers=session["headers"])
    client.post(
        f"{BOOKINGS_URL}/{booking['id']}/cancel", json={"reason": "Ốm"}, headers=gym_trainer
    )

    unread = client.get(f"{NOTIFICATIONS_URL}/unread-count", headers=session["headers"]).json()
    assert unread["unread"] == 1

    notification_id = client.get(NOTIFICATIONS_URL, headers=session["headers"]).json()["items"][0][
        "id"
    ]
    marked = client.post(f"{NOTIFICATIONS_URL}/{notification_id}/read", headers=session["headers"])
    assert marked.status_code == 200
    assert marked.json()["unread"] == 0


def test_mark_all_read(session, gym_trainer) -> None:
    _booked(session, gym_trainer)
    response = client.post(f"{NOTIFICATIONS_URL}/read-all", headers=gym_trainer)
    assert response.status_code == 200
    assert response.json()["unread"] == 0


def test_notifications_are_private(session, gym_trainer, yoga_trainer) -> None:
    _booked(session, gym_trainer)
    assert client.get(NOTIFICATIONS_URL, headers=yoga_trainer).json()["unread"] == 0


def test_notifications_require_token() -> None:
    assert client.get(NOTIFICATIONS_URL).status_code == 401


def test_trainer_cannot_book_as_member(gym_trainer) -> None:
    _set_schedule(gym_trainer)
    start = _slots(gym_trainer)[0]["start_at"]
    response = client.post(
        BOOKINGS_URL,
        json={"trainer_id": TRAINERS["GYM"]["id"], "start_at": start},
        headers=gym_trainer,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MEMBER_NOT_FOUND"
