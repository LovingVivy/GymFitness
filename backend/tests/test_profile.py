"""Integration tests for the member profile, plan catalogue and subscriptions."""

from __future__ import annotations

import base64
import uuid

from fastapi.testclient import TestClient

from app.core import storage
from app.main import app

client = TestClient(app)

PROFILE_URL = "/api/v1/profile"
AVATAR_URL = "/api/v1/profile/avatar"
PLANS_URL = "/api/v1/plans"
SUBSCRIPTIONS_URL = "/api/v1/subscriptions"

# Nhỏ nhất có thể: PNG 1x1 trong suốt.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()


def _plans() -> list[dict]:
    response = client.get(PLANS_URL)
    assert response.status_code == 200
    return response.json()


def _subscribe(session: dict, plan_code: str) -> dict:
    plan = next(item for item in _plans() if item["code"] == plan_code)
    response = client.post(
        SUBSCRIPTIONS_URL, json={"plan_id": plan["id"]}, headers=session["headers"]
    )
    assert response.status_code == 201, response.text
    return {"plan": plan, "body": response.json()}


# --------------------------------------------------------------------------
# Authentication guard
# --------------------------------------------------------------------------


def test_profile_requires_token() -> None:
    assert client.get(PROFILE_URL).status_code == 401


def test_profile_rejects_garbage_token() -> None:
    response = client.get(PROFILE_URL, headers={"Authorization": "Bearer khong-phai-jwt"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_subscriptions_require_token() -> None:
    response = client.post(SUBSCRIPTIONS_URL, json={"plan_id": str(uuid.uuid4())})
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Profile read
# --------------------------------------------------------------------------


def test_register_creates_member_profile(session) -> None:
    response = client.get(PROFILE_URL, headers=session["headers"])
    assert response.status_code == 200

    body = response.json()
    assert body["email"] == session["account"]["email"]
    assert body["full_name"] == "Pytest User"
    assert body["role"] == "USER"
    assert body["status"] == "ACTIVE"
    assert body["member_code"], "đăng ký phải tạo hồ sơ hội viên"
    assert body["member_code"].startswith("MEM")
    assert body["home_branch_name"], "seed phải gán chi nhánh mặc định"
    assert body["avatar_url"] is None
    assert body["membership"] is None, "tài khoản mới chưa có gói"


# --------------------------------------------------------------------------
# Profile update
# --------------------------------------------------------------------------


def test_update_profile_persists_body_stats(session) -> None:
    response = client.patch(
        PROFILE_URL,
        json={
            "height_cm": 175.5,
            "weight_kg": 70.25,
            "experience_level": "intermediate",
            "fitness_goal": "muscle_gain",
            "weekly_training_sessions": 4,
            "emergency_contact_name": "Nguyen Van B",
            "emergency_contact_phone": "0900111222",
        },
        headers=session["headers"],
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["height_cm"] == 175.5
    assert body["weight_kg"] == 70.25
    assert body["experience_level"] == "INTERMEDIATE"
    assert body["fitness_goal"] == "MUSCLE_GAIN"
    assert body["weekly_training_sessions"] == 4
    assert body["emergency_contact_phone"] == "0900111222"

    # Đọc lại phải thấy dữ liệu đã ghi thật vào database.
    again = client.get(PROFILE_URL, headers=session["headers"]).json()
    assert again["height_cm"] == 175.5
    assert again["experience_level"] == "INTERMEDIATE"


def test_update_profile_keeps_omitted_fields(session) -> None:
    client.patch(PROFILE_URL, json={"height_cm": 180}, headers=session["headers"])
    body = client.patch(PROFILE_URL, json={"weight_kg": 80}, headers=session["headers"]).json()
    assert body["height_cm"] == 180, "trường không gửi lên phải giữ nguyên"
    assert body["weight_kg"] == 80


def test_update_profile_validates_ranges(session) -> None:
    for payload in (
        {"height_cm": 10},
        {"weight_kg": 1000},
        {"weekly_training_sessions": 99},
        {"experience_level": "khong-ton-tai"},
        {"fitness_goal": "khong-ton-tai"},
        {"gender": "khong-ton-tai"},
    ):
        response = client.patch(PROFILE_URL, json=payload, headers=session["headers"])
        assert response.status_code == 422, payload


def test_update_profile_rejects_taken_phone(session, purge) -> None:
    other_email = f"pytest.other.{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other User",
            "email": other_email,
            "phone": "0988777666",
            "password": "password123",
        },
    )
    try:
        response = client.patch(
            PROFILE_URL, json={"phone": "0988777666"}, headers=session["headers"]
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "PHONE_EXISTS"
    finally:
        purge(other_email)


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


def test_plan_catalogue_is_seeded() -> None:
    plans = _plans()
    codes = {plan["code"] for plan in plans}
    assert {"GYM_MONTHLY", "GYM_YEARLY", "YOGA_MONTHLY", "YOGA_YEARLY"} <= codes

    monthly = next(plan for plan in plans if plan["code"] == "GYM_MONTHLY")
    assert monthly["activity_type"] == "GYM"
    assert monthly["duration_months"] == 1
    assert monthly["duration_days"] is None
    assert monthly["price"] == 500000.0
    assert isinstance(monthly["price"], float), "giá phải là JSON number để frontend định dạng"


# --------------------------------------------------------------------------
# Subscription lifecycle
# --------------------------------------------------------------------------


def test_subscribe_creates_pending_payment_and_subscription(session) -> None:
    result = _subscribe(session, "GYM_MONTHLY")

    assert result["body"]["status"] == "PENDING"
    assert result["body"]["payment"]["status"] == "PENDING"
    assert result["body"]["payment"]["amount"] == result["plan"]["price"]
    assert result["body"]["payment"]["payment_number"].startswith("IRX")

    profile = client.get(PROFILE_URL, headers=session["headers"]).json()
    assert profile["membership"] is None, "gói PENDING chưa được coi là đang đăng ký"


def test_subscribe_rejects_unknown_plan(session) -> None:
    response = client.post(
        SUBSCRIPTIONS_URL, json={"plan_id": str(uuid.uuid4())}, headers=session["headers"]
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLAN_NOT_FOUND"


def test_mark_paid_activates_membership_and_exposes_days_remaining(session) -> None:
    result = _subscribe(session, "GYM_MONTHLY")
    payment_id = result["body"]["payment"]["id"]

    response = client.post(f"/api/v1/payments/{payment_id}/mark-paid", headers=session["headers"])
    assert response.status_code == 200, response.text

    body = response.json()
    membership = body["membership"]
    assert membership is not None
    assert membership["status"] == "ACTIVE"
    assert membership["plan_code"] == "GYM_MONTHLY"
    assert membership["plan_name"] == "Gym theo tháng"
    assert membership["activity_type"] == "GYM"
    # ADR-003: gói tháng theo lịch tháng thật, nên số ngày phụ thuộc tháng đang mua.
    assert membership["days_remaining"] in (28, 29, 30, 31)
    assert membership["total_days"] == membership["days_remaining"]
    assert membership["start_at"] and membership["end_at"]
    assert membership["end_at"] > membership["start_at"]


def test_yearly_plan_yields_full_year(session) -> None:
    result = _subscribe(session, "YOGA_YEARLY")
    response = client.post(
        f"/api/v1/payments/{result['body']['payment']['id']}/mark-paid",
        headers=session["headers"],
    )
    assert response.status_code == 200

    membership = response.json()["membership"]
    assert membership["plan_code"] == "YOGA_YEARLY"
    assert membership["activity_type"] == "YOGA"
    assert membership["days_remaining"] in (365, 366), "gói năm dùng lịch tháng thật (ADR-003)"


def test_timestamps_are_marked_as_utc(session) -> None:
    """Naive UTC strings would be read as local time by the browser."""
    profile = client.get(PROFILE_URL, headers=session["headers"]).json()
    assert profile["created_at"].endswith("Z")
    assert profile["member_joined_at"].endswith("Z")

    result = _subscribe(session, "GYM_MONTHLY")
    activated = client.post(
        f"/api/v1/payments/{result['body']['payment']['id']}/mark-paid",
        headers=session["headers"],
    ).json()

    assert activated["membership"]["start_at"].endswith("Z")
    assert activated["membership"]["end_at"].endswith("Z")


def test_mark_paid_twice_conflicts(session) -> None:
    result = _subscribe(session, "GYM_MONTHLY")
    payment_id = result["body"]["payment"]["id"]

    first = client.post(f"/api/v1/payments/{payment_id}/mark-paid", headers=session["headers"])
    assert first.status_code == 200

    second = client.post(f"/api/v1/payments/{payment_id}/mark-paid", headers=session["headers"])
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "PAYMENT_NOT_PENDING"


def test_mark_paid_unknown_payment(session) -> None:
    response = client.post(f"/api/v1/payments/{uuid.uuid4()}/mark-paid", headers=session["headers"])
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PAYMENT_NOT_FOUND"


# --------------------------------------------------------------------------
# Avatar
# --------------------------------------------------------------------------


def test_avatar_upload_stores_file_and_returns_url(session) -> None:
    response = client.post(AVATAR_URL, json={"image": PNG_DATA_URL}, headers=session["headers"])
    assert response.status_code == 200, response.text

    avatar_url = response.json()["avatar_url"]
    assert avatar_url and avatar_url.startswith("/api/v1/files/")

    download = client.get(avatar_url, headers=session["headers"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
    assert download.content == PNG_BYTES

    profile = client.get(PROFILE_URL, headers=session["headers"]).json()
    assert profile["avatar_url"] == avatar_url


def test_avatar_is_not_publicly_downloadable(session) -> None:
    avatar_url = client.post(
        AVATAR_URL, json={"image": PNG_DATA_URL}, headers=session["headers"]
    ).json()["avatar_url"]

    assert client.get(avatar_url).status_code == 401


def test_avatar_rejects_non_image_payload(session) -> None:
    text_payload = "data:text/plain;base64," + base64.b64encode(b"day khong phai anh").decode()
    response = client.post(AVATAR_URL, json={"image": text_payload}, headers=session["headers"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FILE"


def test_avatar_rejects_broken_base64(session) -> None:
    response = client.post(
        AVATAR_URL,
        json={"image": "data:image/png;base64,@@@khong-phai-base64-hop-le@@@"},
        headers=session["headers"],
    )
    assert response.status_code == 422


def test_avatar_rejects_oversized_image(session) -> None:
    oversized = PNG_BYTES + b"\x00" * (storage.MAX_AVATAR_BYTES + 1)
    payload = "data:image/png;base64," + base64.b64encode(oversized).decode()

    response = client.post(AVATAR_URL, json={"image": payload}, headers=session["headers"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FILE"


def test_avatar_rejects_mislabelled_content(session) -> None:
    """The declared type is a label; the bytes must really be an image."""
    fake = "data:image/png;base64," + base64.b64encode(b"<svg onload=alert(1)>").decode()
    response = client.post(AVATAR_URL, json={"image": fake}, headers=session["headers"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FILE"


def test_avatar_download_disables_mime_sniffing(session) -> None:
    avatar_url = client.post(
        AVATAR_URL, json={"image": PNG_DATA_URL}, headers=session["headers"]
    ).json()["avatar_url"]

    download = client.get(avatar_url, headers=session["headers"])
    assert download.headers["x-content-type-options"] == "nosniff"


def test_replacing_avatar_retires_previous_file(session, db) -> None:
    first_url = client.post(
        AVATAR_URL, json={"image": PNG_DATA_URL}, headers=session["headers"]
    ).json()["avatar_url"]
    first_id = first_url.rsplit("/", 1)[-1]
    with db.cursor() as cursor:
        cursor.execute("SELECT storage_key FROM file_assets WHERE id = %s", (first_id,))
        first_key = cursor.fetchone()[0]
    assert (storage.storage_root() / first_key).is_file()

    second = client.post(AVATAR_URL, json={"image": PNG_DATA_URL}, headers=session["headers"])
    assert second.status_code == 200, second.text
    second_url = second.json()["avatar_url"]
    assert second_url != first_url

    assert client.get(first_url, headers=session["headers"]).status_code == 404
    assert client.get(second_url, headers=session["headers"]).status_code == 200
    assert not (storage.storage_root() / first_key).exists(), "file cũ phải bị xoá khỏi đĩa"

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM file_assets WHERE id = %s AND deleted_at IS NOT NULL",
            (first_id,),
        )
        assert cursor.fetchone()[0] == 1


def test_file_endpoint_hides_other_users_files(session, purge) -> None:
    """A second account must not read the first account's avatar."""
    avatar_url = client.post(
        AVATAR_URL, json={"image": PNG_DATA_URL}, headers=session["headers"]
    ).json()["avatar_url"]

    other_email = f"pytest.intruder.{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Intruder",
            "email": other_email,
            "phone": f"09{uuid.uuid4().int % 100_000_000:08d}",
            "password": "password123",
        },
    )
    try:
        token = client.post(
            "/api/v1/auth/login", json={"email": other_email, "password": "password123"}
        ).json()["access_token"]

        response = client.get(avatar_url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"
    finally:
        purge(other_email)
