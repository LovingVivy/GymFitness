"""QR checkout, SePay webhook confirmation and the mark-paid guard."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.core.payment_code import extract_payment_number, new_payment_number
from tests.conftest import client

PROFILE_URL = "/api/v1/profile"
WEBHOOK_URL = "/api/v1/payments/webhooks/sepay"
API_KEY = "pytest-sepay-key"


@pytest.fixture
def sepay_key(monkeypatch) -> str:
    monkeypatch.setattr(get_settings(), "sepay_webhook_api_key", API_KEY)
    return API_KEY


@pytest.fixture
def cleanup_events(db) -> Iterator[None]:
    """Unmatched webhook events have no payment, so the account purge misses them."""
    yield
    with db.cursor() as cursor:
        cursor.execute("DELETE FROM payment_events WHERE provider_event_id LIKE 'pytest-%'")


def _subscribe(session: dict, plan_code: str = "GYM_MONTHLY") -> dict:
    plan = next(item for item in client.get("/api/v1/plans").json() if item["code"] == plan_code)
    response = client.post(
        "/api/v1/subscriptions", json={"plan_id": plan["id"]}, headers=session["headers"]
    )
    assert response.status_code == 201, response.text
    return response.json()["payment"]


def _register(email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other Member",
            "email": email,
            "phone": f"09{uuid.uuid4().int % 100_000_000:08d}",
            "password": "password123",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _sepay(content: str, amount: float, **overrides) -> dict:
    body = {
        "id": f"pytest-{uuid.uuid4().hex}",
        "gateway": "MBBank",
        "transactionDate": "2026-09-28 10:00:00",
        "accountNumber": "0123456789",
        "code": None,
        "content": content,
        "transferType": "in",
        "transferAmount": amount,
        "accumulated": 0,
        "subAccount": None,
        "referenceCode": f"FT{uuid.uuid4().hex[:12].upper()}",
        "description": content,
    }
    body.update(overrides)
    return body


def _post_webhook(body: dict, key: str | None = API_KEY):
    headers = {"Authorization": f"Apikey {key}"} if key else {}
    return client.post(WEBHOOK_URL, json=body, headers=headers)


# --------------------------------------------------------------------------
# Transfer code
# --------------------------------------------------------------------------


def test_payment_number_survives_bank_rewriting() -> None:
    code = new_payment_number()
    assert code.startswith("IRX") and code.isalnum() and len(code) == 17

    assert extract_payment_number(f"MBVCB.3278907687.{code}.CT tu 0123") == code
    assert extract_payment_number(f"thanh toan {code.lower()} ironix") == code
    assert extract_payment_number(None, "khong co ma", f"{code[:3]} {code[3:]}") == code
    assert extract_payment_number("chuyen tien an trua") is None


# --------------------------------------------------------------------------
# Checkout + ownership
# --------------------------------------------------------------------------


def test_checkout_returns_transfer_details_to_owner(session) -> None:
    payment = _subscribe(session)

    response = client.get(f"/api/v1/payments/{payment['id']}", headers=session["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["transfer_content"] == payment["payment_number"]
    assert body["amount"] == payment["amount"]
    assert body["expired"] is False
    assert body["expires_at"].endswith("Z")
    assert body["simulation_enabled"] is True, "môi trường test là development"


def test_checkout_builds_vietqr_when_bank_configured(session, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "payment_bank_code", "MB")
    monkeypatch.setattr(settings, "payment_account_no", "0123456789")
    monkeypatch.setattr(settings, "payment_account_name", "IRONIX GYM")
    payment = _subscribe(session)

    body = client.get(f"/api/v1/payments/{payment['id']}", headers=session["headers"]).json()
    assert body["bank"] == {
        "bank_code": "MB",
        "account_no": "0123456789",
        "account_name": "IRONIX GYM",
    }
    assert body["qr_image_url"].startswith("https://img.vietqr.io/image/MB-0123456789-")
    assert f"addInfo={payment['payment_number']}" in body["qr_image_url"]


def test_other_member_cannot_read_or_confirm_payment(session, purge) -> None:
    """Regression: any logged-in account used to be able to mark any payment paid."""
    payment = _subscribe(session)
    other_email = f"pytest.other.{uuid.uuid4().hex[:8]}@example.com"
    try:
        other = _register(other_email)

        read = client.get(f"/api/v1/payments/{payment['id']}", headers=other)
        assert read.status_code == 404

        confirm = client.post(f"/api/v1/payments/{payment['id']}/mark-paid", headers=other)
        assert confirm.status_code == 404
        assert confirm.json()["error"]["code"] == "PAYMENT_NOT_FOUND"
    finally:
        purge(other_email)

    owner_view = client.get(f"/api/v1/payments/{payment['id']}", headers=session["headers"])
    assert owner_view.json()["status"] == "PENDING"


def test_mark_paid_is_disabled_outside_development(session, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "payment_simulation_enabled", False)
    payment = _subscribe(session)

    response = client.post(
        f"/api/v1/payments/{payment['id']}/mark-paid", headers=session["headers"]
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PAYMENT_SIMULATION_DISABLED"

    checkout = client.get(f"/api/v1/payments/{payment['id']}", headers=session["headers"])
    assert checkout.json()["simulation_enabled"] is False


# --------------------------------------------------------------------------
# SePay webhook
# --------------------------------------------------------------------------


def test_webhook_rejects_missing_configuration(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "sepay_webhook_api_key", "")
    response = _post_webhook(_sepay("IRX", 1000))
    assert response.status_code == 503


def test_webhook_rejects_wrong_api_key(sepay_key) -> None:
    assert _post_webhook(_sepay("x", 1000), key="wrong").status_code == 401
    assert _post_webhook(_sepay("x", 1000), key=None).status_code == 401


def test_webhook_activates_membership(session, sepay_key) -> None:
    payment = _subscribe(session)
    body = _sepay(f"MBVCB.123.{payment['payment_number']}.CT", payment["amount"])

    response = _post_webhook(body)
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "message": "paid"}

    checkout = client.get(f"/api/v1/payments/{payment['id']}", headers=session["headers"]).json()
    assert checkout["status"] == "PAID"
    assert checkout["paid_at"]
    assert checkout["simulation_enabled"] is False

    profile = client.get(PROFILE_URL, headers=session["headers"]).json()
    assert profile["membership"]["status"] == "ACTIVE"

    notifications = client.get("/api/v1/notifications", headers=session["headers"]).json()
    assert any(item["notification_type"] == "PAYMENT_PAID" for item in notifications["items"])

    # SePay gửi lại cùng giao dịch: không lỗi, không kích hoạt lần hai.
    again = _post_webhook(body)
    assert again.status_code == 200
    assert again.json()["message"] == "duplicate"


def test_webhook_keeps_underpaid_payment_pending(session, sepay_key) -> None:
    payment = _subscribe(session)
    short = float(Decimal(str(payment["amount"])) - 1000)

    response = _post_webhook(_sepay(payment["payment_number"], short))
    assert response.status_code == 200
    assert response.json()["message"].startswith("AMOUNT_TOO_LOW")

    checkout = client.get(f"/api/v1/payments/{payment['id']}", headers=session["headers"]).json()
    assert checkout["status"] == "PENDING"
    assert client.get(PROFILE_URL, headers=session["headers"]).json()["membership"] is None


def test_webhook_acknowledges_unrelated_transfers(sepay_key, cleanup_events) -> None:
    no_code = _post_webhook(_sepay("chuyen tien an trua", 50000))
    assert no_code.status_code == 200
    assert no_code.json()["message"] == "NO_PAYMENT_CODE"

    unknown = _post_webhook(_sepay(new_payment_number(), 50000))
    assert unknown.json()["message"] == "PAYMENT_NOT_FOUND"

    outgoing = _post_webhook(_sepay(new_payment_number(), 50000, transferType="out"))
    assert outgoing.json()["message"] == "IGNORED_OUTGOING_TRANSFER"


def test_plan_and_pt_sessions_share_one_payment(session, sepay_key) -> None:
    """ADR-014: một mã QR cho cả gói hội viên lẫn lượt PT mua kèm."""
    plan = next(
        item for item in client.get("/api/v1/plans").json() if item["code"] == "GYM_MONTHLY"
    )
    created = client.post(
        "/api/v1/subscriptions",
        json={"plan_id": plan["id"], "pt_sessions": 3},
        headers=session["headers"],
    )
    assert created.status_code == 201, created.text
    payment = created.json()["payment"]
    assert created.json()["pt_sessions"] == 3
    assert payment["amount"] == plan["price"] + 3 * 200_000

    response = _post_webhook(_sepay(payment["payment_number"], payment["amount"]))
    assert response.json()["message"] == "paid"

    profile = client.get(PROFILE_URL, headers=session["headers"]).json()
    assert profile["membership"]["status"] == "ACTIVE"
    wallet = client.get("/api/v1/pt-credits", headers=session["headers"]).json()
    assert (wallet["purchased"], wallet["available"]) == (3, 3)

    notifications = client.get("/api/v1/notifications", headers=session["headers"]).json()
    paid = next(n for n in notifications["items"] if n["notification_type"] == "PAYMENT_PAID")
    assert "3 buổi PT" in paid["body"]


def test_webhook_credits_pt_sessions(session, sepay_key) -> None:
    created = client.post(
        "/api/v1/pt-credits/purchase", json={"quantity": 2}, headers=session["headers"]
    )
    assert created.status_code == 201, created.text
    purchase = created.json()

    response = _post_webhook(_sepay(purchase["payment_number"], purchase["amount"]))
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "paid"

    wallet = client.get("/api/v1/pt-credits", headers=session["headers"]).json()
    assert wallet["purchased"] == 2
    assert wallet["available"] == 2
