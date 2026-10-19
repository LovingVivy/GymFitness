"""Admin area: guard, accounts, plans, check-in logs and revenue report."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date, timedelta

import pytest

from app.core.config import get_settings
from app.services import admin as admin_service
from tests.conftest import client, purge_user

ADMIN_URL = "/api/v1/admin"


@pytest.fixture
def admin(session, db) -> dict:
    """A fresh account promoted to ADMIN (independent of the real default admin)."""
    with db.cursor() as cursor:
        cursor.execute("UPDATE users SET role = 'ADMIN' WHERE id = %s", (session["user"]["id"],))
    return session


@pytest.fixture
def created_users(db) -> Iterator[list[str]]:
    """Ids of accounts created through the admin API, purged afterwards."""
    ids: list[str] = []
    yield ids
    for user_id in ids:
        purge_user(db, user_id)


@pytest.fixture(autouse=True)
def cleanup_plans(db) -> Iterator[None]:
    yield
    with db.cursor() as cursor:
        cursor.execute(
            "DELETE FROM audit_logs WHERE entity_type = 'membership_plan' AND entity_id IN "
            "(SELECT id FROM membership_plans WHERE code LIKE 'PYTEST_%%')"
        )
        cursor.execute("DELETE FROM membership_plans WHERE code LIKE 'PYTEST_%%'")


def _new_user(admin: dict, created: list[str], **overrides) -> dict:
    body = {
        "full_name": "Admin Tạo",
        "email": f"pytest.admin.{uuid.uuid4().hex[:10]}@example.com",
        "password": "password123",
        "role": "USER",
    }
    body.update(overrides)
    response = client.post(f"{ADMIN_URL}/users", json=body, headers=admin["headers"])
    assert response.status_code == 201, response.text
    created.append(response.json()["id"])
    return response.json()


def _subscribe_and_pay(session: dict, plan_code: str = "GYM_MONTHLY") -> dict:
    plan = next(item for item in client.get("/api/v1/plans").json() if item["code"] == plan_code)
    created = client.post(
        "/api/v1/subscriptions", json={"plan_id": plan["id"]}, headers=session["headers"]
    )
    assert created.status_code == 201, created.text
    paid = client.post(
        f"/api/v1/payments/{created.json()['payment']['id']}/mark-paid",
        headers=session["headers"],
    )
    assert paid.status_code == 200, paid.text
    return created.json()["payment"]


# --------------------------------------------------------------------------
# Guard and default admin
# --------------------------------------------------------------------------


def test_admin_area_is_admin_only(session) -> None:
    for path in (
        "/overview",
        "/users",
        "/plans",
        "/checkins",
        "/revenue",
        "/members/growth",
        "/payments",
        "/products",
    ):
        assert client.get(f"{ADMIN_URL}{path}", headers=session["headers"]).status_code == 403
        assert client.get(f"{ADMIN_URL}{path}").status_code == 401


def test_default_admin_bootstrap_is_idempotent(db, monkeypatch) -> None:
    settings = get_settings()
    username = f"pytest_admin_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    monkeypatch.setattr(settings, "admin_username", username)
    monkeypatch.setattr(settings, "admin_email", email)
    monkeypatch.setattr(settings, "admin_default_password", "bootstrap-pass-123")
    try:
        from app.db.session import SessionLocal

        with SessionLocal() as session_db:
            assert admin_service.ensure_default_admin(session_db) is True
            assert admin_service.ensure_default_admin(session_db) is False

        # Đăng nhập được bằng tên đăng nhập, không chỉ bằng email.
        response = client.post(
            "/api/v1/auth/login", json={"email": username, "password": "bootstrap-pass-123"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["user"]["role"] == "ADMIN"
    finally:
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            row = cursor.fetchone()
        if row:
            purge_user(db, row[0])


def test_bootstrap_skipped_without_password(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "admin_default_password", "")
    assert admin_service.ensure_default_admin(None) is False


def test_overview_counts(admin) -> None:
    body = client.get(f"{ADMIN_URL}/overview", headers=admin["headers"]).json()
    assert set(body) >= {"members", "trainers", "active_members", "checkins_today", "inside_now"}
    assert body["members"] >= 0


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


def test_admin_creates_member_and_member_can_log_in(admin, created_users) -> None:
    user = _new_user(admin, created_users, username="pytest.member", phone=None)
    assert user["role"] == "USER"
    assert user["member_code"].startswith("MEM")

    for identifier in (user["email"], "pytest.member"):
        login = client.post(
            "/api/v1/auth/login", json={"email": identifier, "password": "password123"}
        )
        assert login.status_code == 200, login.text


def test_admin_creates_trainer_with_specialties(admin, created_users) -> None:
    trainer = _new_user(
        admin,
        created_users,
        role="PT",
        specialties=["YOGA", "FLEXIBILITY"],
        hourly_rate=350000,
    )
    assert trainer["employee_code"].startswith("PT")
    assert trainer["specialties"] == ["FLEXIBILITY", "YOGA"]
    assert trainer["hourly_rate"] == 350000


def test_trainer_requires_specialty(admin) -> None:
    response = client.post(
        f"{ADMIN_URL}/users",
        json={
            "full_name": "PT",
            "email": "pytest.nospec@example.com",
            "password": "password123",
            "role": "PT",
        },
        headers=admin["headers"],
    )
    assert response.status_code == 422


def test_duplicate_email_is_rejected(admin, created_users) -> None:
    user = _new_user(admin, created_users)
    response = client.post(
        f"{ADMIN_URL}/users",
        json={"full_name": "X", "email": user["email"], "password": "password123"},
        headers=admin["headers"],
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_EXISTS"


def test_list_search_and_filter(admin, created_users) -> None:
    user = _new_user(admin, created_users, full_name="Tìm Kiếm Độc Nhất")
    body = client.get(
        f"{ADMIN_URL}/users", params={"search": "Độc Nhất"}, headers=admin["headers"]
    ).json()
    assert [item["id"] for item in body["items"]] == [user["id"]]
    assert body["total"] == 1

    trainers = client.get(
        f"{ADMIN_URL}/users", params={"role": "PT"}, headers=admin["headers"]
    ).json()
    assert trainers["items"] and all(item["role"] == "PT" for item in trainers["items"])


def test_update_suspend_and_reset_password(admin, created_users) -> None:
    user = _new_user(admin, created_users)
    url = f"{ADMIN_URL}/users/{user['id']}"

    updated = client.patch(
        url,
        json={"full_name": "Tên Mới", "phone": "0900000001", "status": "SUSPENDED"},
        headers=admin["headers"],
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["full_name"] == "Tên Mới"
    assert updated.json()["status"] == "SUSPENDED"

    blocked = client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": "password123"}
    )
    assert blocked.status_code == 403, "tài khoản bị khoá không đăng nhập được"

    client.patch(url, json={"status": "ACTIVE"}, headers=admin["headers"])
    reset = client.post(
        f"{url}/password", json={"password": "newpassword456"}, headers=admin["headers"]
    )
    assert reset.status_code == 204
    login = client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": "newpassword456"}
    )
    assert login.status_code == 200


def test_admin_cannot_lock_or_delete_self(admin) -> None:
    my_id = admin["user"]["id"]
    locked = client.patch(
        f"{ADMIN_URL}/users/{my_id}", json={"status": "SUSPENDED"}, headers=admin["headers"]
    )
    assert locked.status_code == 409
    deleted = client.delete(f"{ADMIN_URL}/users/{my_id}", headers=admin["headers"])
    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "CANNOT_DELETE_SELF"


def test_delete_frees_email_and_hides_account(admin, created_users) -> None:
    user = _new_user(admin, created_users)

    response = client.delete(f"{ADMIN_URL}/users/{user['id']}", headers=admin["headers"])
    assert response.status_code == 204

    search = client.get(
        f"{ADMIN_URL}/users", params={"search": user["email"]}, headers=admin["headers"]
    ).json()
    assert search["total"] == 0

    login = client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": "password123"}
    )
    assert login.status_code == 401

    again = _new_user(admin, created_users, email=user["email"])
    assert again["id"] != user["id"], "email đã được giải phóng để đăng ký lại"


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


def test_plan_crud_and_catalogue(admin) -> None:
    body = {
        "code": f"pytest_{uuid.uuid4().hex[:6]}",
        "name": "Gym 3 tháng",
        "activity_type": "GYM",
        "duration_months": 3,
        "price": 1350000,
        "is_active": True,
    }
    created = client.post(f"{ADMIN_URL}/plans", json=body, headers=admin["headers"])
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["code"] == body["code"].upper()

    public = {item["code"] for item in client.get("/api/v1/plans").json()}
    assert plan["code"] in public, "gói mới mở bán ngay trên trang đăng ký"

    hidden = client.put(
        f"{ADMIN_URL}/plans/{plan['id']}",
        json={**body, "price": 1200000, "is_active": False},
        headers=admin["headers"],
    )
    assert hidden.status_code == 200
    assert hidden.json()["price"] == 1200000
    assert plan["code"] not in {item["code"] for item in client.get("/api/v1/plans").json()}

    assert (
        client.delete(f"{ADMIN_URL}/plans/{plan['id']}", headers=admin["headers"]).status_code
        == 204
    )
    remaining = {
        item["id"] for item in client.get(f"{ADMIN_URL}/plans", headers=admin["headers"]).json()
    }
    assert plan["id"] not in remaining


def test_plan_needs_exactly_one_duration(admin) -> None:
    response = client.post(
        f"{ADMIN_URL}/plans",
        json={
            "code": "PYTEST_BAD",
            "name": "Sai",
            "activity_type": "GYM",
            "duration_months": 1,
            "duration_days": 30,
            "price": 1,
        },
        headers=admin["headers"],
    )
    assert response.status_code == 422


def test_duplicate_plan_code_is_rejected(admin) -> None:
    body = {
        "code": "GYM_MONTHLY",
        "name": "Trùng",
        "activity_type": "GYM",
        "duration_days": 7,
        "price": 1,
    }
    response = client.post(f"{ADMIN_URL}/plans", json=body, headers=admin["headers"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PLAN_CODE_EXISTS"


# --------------------------------------------------------------------------
# Check-in logs
# --------------------------------------------------------------------------


def test_manual_checkin_and_checkout(admin, second_member_with_plan) -> None:
    code = second_member_with_plan["member_code"]

    created = client.post(
        f"{ADMIN_URL}/checkins", json={"identifier": code}, headers=admin["headers"]
    )
    assert created.status_code == 201, created.text
    assert created.json()["member_name"] == "Check In Member"

    twice = client.post(
        f"{ADMIN_URL}/checkins", json={"identifier": code}, headers=admin["headers"]
    )
    assert twice.status_code == 409
    assert twice.json()["error"]["code"] == "ALREADY_INSIDE"

    inside = client.get(
        f"{ADMIN_URL}/checkins",
        params={"inside_only": True, "search": code},
        headers=admin["headers"],
    ).json()
    assert [item["id"] for item in inside["items"]] == [created.json()["id"]]
    assert inside["items"][0]["check_out_at"] is None

    out = client.post(
        f"{ADMIN_URL}/checkins/{created.json()['id']}/checkout", headers=admin["headers"]
    )
    assert out.status_code == 204

    history = client.get(
        f"{ADMIN_URL}/checkins",
        params={"search": code, "date_from": date.today().isoformat()},
        headers=admin["headers"],
    ).json()
    assert history["items"][0]["check_out_at"] is not None
    assert history["items"][0]["duration_minutes"] == 0


def test_checkin_requires_active_plan(admin, created_users) -> None:
    user = _new_user(admin, created_users)
    response = client.post(
        f"{ADMIN_URL}/checkins", json={"identifier": user["member_code"]}, headers=admin["headers"]
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_ACTIVE_SUBSCRIPTION"


def test_checkin_unknown_member(admin) -> None:
    response = client.post(
        f"{ADMIN_URL}/checkins", json={"identifier": "MEM999999"}, headers=admin["headers"]
    )
    assert response.status_code == 404


@pytest.fixture
def second_member_with_plan(purge) -> Iterator[dict]:
    email = f"pytest.checkin.{uuid.uuid4().hex[:8]}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Check In Member", "email": email, "password": "password123"},
    )
    assert registered.status_code == 201, registered.text
    session = {"headers": {"Authorization": f"Bearer {registered.json()['access_token']}"}}
    _subscribe_and_pay(session)
    profile = client.get("/api/v1/profile", headers=session["headers"]).json()
    yield {"member_code": profile["member_code"], **session}
    purge(email)


# --------------------------------------------------------------------------
# Revenue
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("period", "size", "label_prefix"),
    [("WEEK", 12, "Tuần "), ("MONTH", 12, "T"), ("QUARTER", 8, "Q"), ("YEAR", 5, "20")],
)
def test_revenue_buckets_are_zero_filled(admin, period, size, label_prefix) -> None:
    body = client.get(
        f"{ADMIN_URL}/revenue", params={"period": period}, headers=admin["headers"]
    ).json()
    assert body["period"] == period
    assert len(body["buckets"]) == size
    assert all(bucket["label"].startswith(label_prefix) for bucket in body["buckets"])
    starts = [bucket["period_start"] for bucket in body["buckets"]]
    assert starts == sorted(starts)


@pytest.mark.parametrize("period", ["WEEK", "MONTH", "QUARTER", "YEAR"])
def test_paid_payment_counts_in_current_period(admin, period) -> None:
    def current() -> dict:
        report = client.get(
            f"{ADMIN_URL}/revenue", params={"period": period}, headers=admin["headers"]
        ).json()
        return report["buckets"][-1]

    before = current()
    payment = _subscribe_and_pay(admin, "GYM_MONTHLY")
    after = current()

    assert after["total"] - before["total"] == pytest.approx(payment["amount"])
    assert after["membership_total"] - before["membership_total"] == pytest.approx(
        payment["amount"]
    )
    assert after["payment_count"] == before["payment_count"] + 1


# --------------------------------------------------------------------------
# Member growth
# --------------------------------------------------------------------------


def test_overview_reports_growth_fields(admin) -> None:
    body = client.get(f"{ADMIN_URL}/overview", headers=admin["headers"]).json()
    assert set(body) >= {
        "new_members_this_month",
        "new_members_last_month",
        "member_growth_percent",
        "revenue_last_month",
        "revenue_growth_percent",
        "products",
    }
    assert body["new_members_this_month"] <= body["members"]


@pytest.mark.parametrize(("period", "size"), [("WEEK", 12), ("MONTH", 12), ("YEAR", 5)])
def test_member_growth_counts_new_member(admin, created_users, period, size) -> None:
    def report() -> dict:
        response = client.get(
            f"{ADMIN_URL}/members/growth", params={"period": period}, headers=admin["headers"]
        )
        assert response.status_code == 200, response.text
        return response.json()

    before = report()
    _new_user(admin, created_users)
    after = report()

    assert len(after["buckets"]) == size
    assert after["buckets"][-1]["new_members"] == before["buckets"][-1]["new_members"] + 1
    assert after["total_members"] == before["total_members"] + 1
    assert after["buckets"][-1]["total_members"] == after["total_members"]
    # Tổng cộng dồn không bao giờ giảm qua các kỳ.
    totals = [bucket["total_members"] for bucket in after["buckets"]]
    assert totals == sorted(totals)


def test_member_growth_ignores_trainers(admin, created_users) -> None:
    def total() -> int:
        return client.get(f"{ADMIN_URL}/members/growth", headers=admin["headers"]).json()[
            "total_members"
        ]

    before = total()
    _new_user(admin, created_users, role="PT", specialties=["GYM"])
    assert total() == before


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------


@pytest.fixture
def pending_payment(db, purge) -> Iterator[dict]:
    """A member with an unpaid subscription + 2 PT sessions in one payment."""
    email = f"pytest.pay.{uuid.uuid4().hex[:8]}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Pending Payer", "email": email, "password": "password123"},
    )
    assert registered.status_code == 201, registered.text
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    plan = next(
        item for item in client.get("/api/v1/plans").json() if item["code"] == "GYM_MONTHLY"
    )
    created = client.post(
        "/api/v1/subscriptions", json={"plan_id": plan["id"], "pt_sessions": 2}, headers=headers
    )
    assert created.status_code == 201, created.text
    payment = created.json()["payment"]
    yield {"headers": headers, "payment": payment}
    with db.cursor() as cursor:
        cursor.execute(
            "DELETE FROM audit_logs WHERE entity_type = 'payment' AND entity_id = %s",
            (payment["id"],),
        )
    purge(email)


def _find_payment(admin: dict, payment: dict, **params) -> dict:
    body = client.get(
        f"{ADMIN_URL}/payments",
        params={"search": payment["payment_number"], **params},
        headers=admin["headers"],
    ).json()
    assert body["total"] == len(body["items"])
    return body


def test_payment_list_finds_pending_payment(admin, pending_payment) -> None:
    body = _find_payment(admin, pending_payment["payment"])
    assert body["total"] == 1
    item = body["items"][0]
    assert item["status"] == "PENDING"
    assert item["purpose"] == "MEMBERSHIP"
    assert item["member_name"] == "Pending Payer"
    assert item["plan_name"] == "Gym theo tháng"
    assert item["pt_quantity"] == 2
    assert body["paid_total"] == 0

    assert _find_payment(admin, pending_payment["payment"], status="PAID")["total"] == 0
    assert _find_payment(admin, pending_payment["payment"], purpose="PT_CREDIT")["total"] == 0
    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    assert _find_payment(admin, pending_payment["payment"], date_from=tomorrow)["total"] == 0


def test_admin_confirms_payment_and_grants_benefits(admin, pending_payment, db) -> None:
    payment = pending_payment["payment"]
    response = client.post(
        f"{ADMIN_URL}/payments/{payment['id']}/confirm",
        json={"method": "CASH"},
        headers=admin["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "PAID"
    assert body["method"] == "CASH"
    assert body["paid_at"]

    profile = client.get("/api/v1/profile", headers=pending_payment["headers"]).json()
    assert profile["membership"]["status"] == "ACTIVE"
    assert profile["pt_credits"]["remaining"] == 2

    listed = _find_payment(admin, payment)
    assert listed["paid_total"] == pytest.approx(payment["amount"])

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT actor_user_id FROM audit_logs WHERE action = 'PAYMENT_CONFIRM' "
            "AND entity_id = %s",
            (payment["id"],),
        )
        assert cursor.fetchone()[0] == admin["user"]["id"]

    again = client.post(f"{ADMIN_URL}/payments/{payment['id']}/confirm", headers=admin["headers"])
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "PAYMENT_NOT_PENDING"


def test_admin_voids_pending_payment(admin, pending_payment) -> None:
    payment = pending_payment["payment"]
    response = client.post(
        f"{ADMIN_URL}/payments/{payment['id']}/void",
        json={"reason": "Khách đổi ý"},
        headers=admin["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "VOID"
    assert response.json()["failure_reason"] == "Khách đổi ý"

    profile = client.get("/api/v1/profile", headers=pending_payment["headers"]).json()
    assert profile["membership"] is None
    assert profile["pt_credits"]["remaining"] == 0

    # Giao dịch đã huỷ không xác nhận hay huỷ lại được, hội viên cũng không tự kích hoạt được.
    for action in ("confirm", "void"):
        retry = client.post(
            f"{ADMIN_URL}/payments/{payment['id']}/{action}", headers=admin["headers"]
        )
        assert retry.status_code == 409, retry.text
    owner = client.post(
        f"/api/v1/payments/{payment['id']}/mark-paid", headers=pending_payment["headers"]
    )
    assert owner.status_code == 409


def test_payment_actions_on_unknown_payment(admin) -> None:
    for action in ("confirm", "void"):
        response = client.post(
            f"{ADMIN_URL}/payments/{uuid.uuid4()}/{action}", headers=admin["headers"]
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PAYMENT_NOT_FOUND"


# --------------------------------------------------------------------------
# Shop
# --------------------------------------------------------------------------


@pytest.fixture
def cleanup_products(db) -> Iterator[None]:
    yield
    with db.cursor() as cursor:
        cursor.execute("SELECT id FROM products WHERE name LIKE 'Pytest %%'")
        product_ids = [row[0] for row in cursor.fetchall()]
        for product_id in product_ids:
            cursor.execute(
                "DELETE FROM inventory_movements WHERE variant_id IN "
                "(SELECT id FROM product_variants WHERE product_id = %s)",
                (product_id,),
            )
            cursor.execute("DELETE FROM product_variants WHERE product_id = %s", (product_id,))
            cursor.execute(
                "DELETE FROM audit_logs WHERE entity_type = 'product' AND entity_id = %s",
                (product_id,),
            )
            cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        cursor.execute("DELETE FROM product_categories WHERE name LIKE 'Pytest %%'")


def _product_body(**overrides) -> dict:
    body = {
        "name": f"Pytest Găng tay {uuid.uuid4().hex[:6]}",
        "sku": f"PYTEST-{uuid.uuid4().hex[:8].upper()}",
        "category_name": "Pytest Phụ kiện",
        "activity_type": "GYM",
        "description": "Đệm gel",
        "price": 250000,
        "stock_quantity": 10,
        "badge": "Mới",
        "art": "gloves",
    }
    body.update(overrides)
    return body


def _public_skus() -> set[str]:
    response = client.get("/api/v1/products")
    assert response.status_code == 200, response.text
    return {item["sku"] for item in response.json()}


def test_public_products_need_no_login() -> None:
    items = client.get("/api/v1/products").json()
    assert all(item["price"] >= 0 and item["available_quantity"] >= 0 for item in items)


def test_admin_product_lifecycle(admin, db, cleanup_products) -> None:
    body = _product_body()
    created = client.post(f"{ADMIN_URL}/products", json=body, headers=admin["headers"])
    assert created.status_code == 201, created.text
    product = created.json()
    assert product["sku"] == body["sku"]
    assert product["slug"].startswith("pytest-gang-tay-")
    assert product["stock_quantity"] == 10
    assert product["badge"] == "Mới"
    assert product["category_name"] == "Pytest Phụ kiện"
    assert body["sku"] in _public_skus()

    listed = client.get(
        f"{ADMIN_URL}/products", params={"search": body["sku"]}, headers=admin["headers"]
    ).json()
    assert [item["id"] for item in listed["items"]] == [product["id"]]

    # Đổi giá + tồn kho, bỏ nhãn; SKU bỏ trống thì giữ nguyên.
    updated = client.put(
        f"{ADMIN_URL}/products/{product['id']}",
        json=_product_body(name=body["name"], sku=None, price=199000, stock_quantity=4, badge=None),
        headers=admin["headers"],
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["sku"] == body["sku"]
    assert updated.json()["price"] == 199000
    assert updated.json()["stock_quantity"] == 4
    assert updated.json()["badge"] is None

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT im.movement_type, im.quantity_delta, im.stock_balance "
            "FROM inventory_movements im JOIN product_variants v ON v.id = im.variant_id "
            "WHERE v.product_id = %s ORDER BY im.created_at",
            (product["id"],),
        )
        assert cursor.fetchall() == (("IMPORT", 10, 10), ("ADJUST", -6, 4))

    # Ẩn khỏi cửa hàng nhưng vẫn thấy trong trang quản trị.
    hidden = client.put(
        f"{ADMIN_URL}/products/{product['id']}",
        json=_product_body(name=body["name"], sku=body["sku"], status="INACTIVE"),
        headers=admin["headers"],
    )
    assert hidden.status_code == 200
    assert body["sku"] not in _public_skus()

    product_url = f"{ADMIN_URL}/products/{product['id']}"
    assert client.delete(product_url, headers=admin["headers"]).status_code == 204
    assert client.delete(product_url, headers=admin["headers"]).status_code == 404
    # SKU được giải phóng sau khi xoá.
    reused = client.post(
        f"{ADMIN_URL}/products", json=_product_body(sku=body["sku"]), headers=admin["headers"]
    )
    assert reused.status_code == 201, reused.text


def test_product_sku_must_be_unique(admin, cleanup_products) -> None:
    body = _product_body()
    first = client.post(f"{ADMIN_URL}/products", json=body, headers=admin["headers"])
    assert first.status_code == 201, first.text
    duplicate = client.post(
        f"{ADMIN_URL}/products", json=_product_body(sku=body["sku"]), headers=admin["headers"]
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "SKU_EXISTS"


def test_product_without_sku_gets_one(admin, cleanup_products) -> None:
    created = client.post(
        f"{ADMIN_URL}/products", json=_product_body(sku=None), headers=admin["headers"]
    )
    assert created.status_code == 201, created.text
    assert created.json()["sku"].startswith("SP-")


@pytest.mark.parametrize(
    "overrides",
    [
        {"price": -1},
        {"stock_quantity": -1},
        {"name": "  "},
        {"activity_type": "SWIM"},
        {"sku": "a b"},
    ],
)
def test_product_validation(admin, overrides) -> None:
    response = client.post(
        f"{ADMIN_URL}/products", json=_product_body(**overrides), headers=admin["headers"]
    )
    assert response.status_code == 422


def test_update_unknown_product(admin) -> None:
    response = client.put(
        f"{ADMIN_URL}/products/{uuid.uuid4()}", json=_product_body(), headers=admin["headers"]
    )
    assert response.status_code == 404
