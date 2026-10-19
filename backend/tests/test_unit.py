"""Unit tests: pure functions and modules that need no database.

Integration tests (``test_*.py`` next to this file) cover the API end to end on
MySQL; these check the building blocks in isolation: permissions, TOTP, tokens,
cache, rate limiting, exports, PDF, logging, mail and service helpers.
"""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal

import fakeredis
import pytest
from openpyxl import load_workbook

from app.core import cache, exporters, mailer, pdf, rate_limit, redis_client, security, totp
from app.core.config import get_settings
from app.core.exporters import Column
from app.core.logging import JsonFormatter, request_id_var
from app.core.permissions import (
    Permission,
    can_manage_account,
    has_permission,
    permissions_for,
    sorted_permissions,
)
from app.services import admin as admin_service
from app.services import exports as exports_service
from app.services import invoices as invoices_service
from app.services import shop as shop_service
from tests.conftest import client

# Bản gốc, giữ lại trước khi fixture ``outbox`` thay thế để test bắt email.
_REAL_DELIVER = mailer.deliver


@pytest.fixture
def fake_redis():
    server = fakeredis.FakeRedis(decode_responses=True)
    redis_client.use_client_for_tests(server)
    yield server
    redis_client.use_client_for_tests(None)


# --------------------------------------------------------------------------
# RBAC
# --------------------------------------------------------------------------


def test_admin_has_every_permission() -> None:
    assert permissions_for("ADMIN") == frozenset(Permission)


def test_manager_runs_operations_but_not_staff_plans_voids_or_audit() -> None:
    for allowed in (
        Permission.DASHBOARD_VIEW,
        Permission.REPORTS_EXPORT,
        Permission.USERS_MANAGE_MEMBERS,
        Permission.PAYMENTS_CONFIRM,
        Permission.PRODUCTS_MANAGE,
        Permission.CHECKINS_MANAGE,
    ):
        assert has_permission("MANAGER", allowed)
    for denied in (
        Permission.USERS_MANAGE_STAFF,
        Permission.USERS_DELETE,
        Permission.PLANS_MANAGE,
        Permission.PAYMENTS_VOID,
        Permission.AUDIT_VIEW,
    ):
        assert not has_permission("MANAGER", denied)


@pytest.mark.parametrize("role", ["USER", "PT", None, "UNKNOWN"])
def test_members_trainers_and_unknown_roles_have_no_admin_permission(role) -> None:
    assert permissions_for(role) == frozenset()
    assert sorted_permissions(role) == []


def test_account_management_is_scoped_by_target_role() -> None:
    assert can_manage_account("MANAGER", "USER")
    for staff in ("PT", "MANAGER", "ADMIN"):
        assert not can_manage_account("MANAGER", staff)
        assert can_manage_account("ADMIN", staff)
    assert not can_manage_account("USER", "USER")


# --------------------------------------------------------------------------
# TOTP and tokens
# --------------------------------------------------------------------------

# RFC 6238, phụ lục B: khoá ASCII "12345678901234567890", SHA-1.
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


@pytest.mark.parametrize(
    ("moment", "code"),
    [(59, "287082"), (1111111109, "081804"), (1234567890, "005924"), (2000000000, "279037")],
)
def test_totp_matches_rfc_6238_vectors(moment, code) -> None:
    assert totp.code_at(RFC_SECRET, moment) == code


def test_totp_accepts_one_step_of_clock_drift_only() -> None:
    now = 1_700_000_000
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, now - 30), now)
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, now + 30), now)
    assert not totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, now - 90), now)
    assert not totp.verify(RFC_SECRET, "12345", now)
    assert not totp.verify(RFC_SECRET, "abcdef", now)


def test_totp_secret_round_trips_through_encryption() -> None:
    secret = totp.new_secret()
    assert len(secret) == 32
    stored = totp.encrypt_secret(secret)
    assert secret not in stored
    assert totp.decrypt_secret(stored) == secret
    assert totp.decrypt_secret("not-a-token") is None


def test_provisioning_uri_and_qr() -> None:
    uri = totp.provisioning_uri(RFC_SECRET, "hoi.vien@example.com")
    assert uri.startswith("otpauth://totp/")
    assert f"secret={RFC_SECRET}" in uri
    assert "hoi.vien%40example.com" in uri
    assert totp.qr_svg(uri).startswith("<svg")


def test_purpose_tokens_are_never_accepted_as_access_tokens() -> None:
    token = security.create_purpose_token("user-1", "2fa_login", 5)
    assert security.decode_purpose_token(token, "2fa_login")["sub"] == "user-1"
    with pytest.raises(ValueError):
        security.decode_access_token(token)
    with pytest.raises(ValueError):
        security.decode_purpose_token(token, "2fa_setup")
    access = security.create_access_token("user-1", "USER")
    assert security.decode_access_token(access)["role"] == "USER"
    with pytest.raises(ValueError):
        security.decode_purpose_token(access, "2fa_login")


def test_tampered_token_is_rejected() -> None:
    token = security.create_access_token("user-1", "USER")
    header, payload, signature = token.split(".")
    with pytest.raises(ValueError):
        security.decode_access_token(f"{header}.{payload}.{signature[::-1]}")


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------


@pytest.fixture
def cache_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "cache_enabled", True)
    cache.clear_local()
    yield
    cache.clear_local()


def _counting_loader(value):
    calls = []

    def load():
        calls.append(1)
        return value

    return load, calls


def test_cache_is_a_pass_through_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "cache_enabled", False)
    load, calls = _counting_loader([1, 2])
    cache.get_or_load("catalog", "k", 60, load, list[int])
    cache.get_or_load("catalog", "k", 60, load, list[int])
    assert len(calls) == 2


def test_memory_cache_reads_through_and_invalidates_by_namespace(cache_on) -> None:
    load, calls = _counting_loader({"a": 1})
    assert cache.get_or_load("catalog", "k", 60, load, dict[str, int]) == {"a": 1}
    assert cache.get_or_load("catalog", "k", 60, load, dict[str, int]) == {"a": 1}
    assert len(calls) == 1

    cache.invalidate("reports")
    cache.get_or_load("catalog", "k", 60, load, dict[str, int])
    assert len(calls) == 1, "namespace khác không bị ảnh hưởng"

    cache.invalidate("catalog")
    cache.get_or_load("catalog", "k", 60, load, dict[str, int])
    assert len(calls) == 2


def test_redis_cache_stores_json_with_ttl(cache_on, fake_redis) -> None:
    load, calls = _counting_loader([Decimal("1.5")])
    assert cache.get_or_load("reports", "x", 30, load, list[Decimal]) == [Decimal("1.5")]
    assert cache.get_or_load("reports", "x", 30, load, list[Decimal]) == [Decimal("1.5")]
    assert len(calls) == 1
    keys = fake_redis.keys("gf:cache:reports:*")
    assert len(keys) == 1
    assert 0 < fake_redis.ttl(keys[0]) <= 30

    cache.invalidate("reports")
    assert fake_redis.get("gf:cache:ver:reports") == "1"
    cache.get_or_load("reports", "x", 30, load, list[Decimal])
    assert len(calls) == 2


def test_cache_falls_back_to_loader_when_redis_fails(cache_on, fake_redis, monkeypatch) -> None:
    import redis

    def broken(*_args, **_kwargs):
        raise redis.ConnectionError("down")

    monkeypatch.setattr(fake_redis, "get", broken)
    load, calls = _counting_loader([3])
    assert cache.get_or_load("catalog", "y", 60, load, list[int]) == [3]
    assert len(calls) == 1


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_rate_limit_rules_by_path() -> None:
    settings = get_settings()
    assert rate_limit.rule_for("POST", "/api/v1/auth/login").limit == (
        settings.rate_limit_auth_per_minute
    )
    assert rate_limit.rule_for("POST", "/api/v1/auth/forgot-password").name == "auth"
    assert rate_limit.rule_for("GET", "/api/v1/plans").name == "api"
    assert rate_limit.rule_for("POST", "/api/v1/payments/webhooks/sepay") is None
    assert rate_limit.rule_for("GET", "/health/live") is None


def test_memory_counter_resets_each_window() -> None:
    rate_limit.reset_local()
    rule = rate_limit.Rule("unit", 2)
    assert rate_limit.hit(rule, "1.2.3.4", now=120.0)[0] == 1
    assert rate_limit.hit(rule, "1.2.3.4", now=130.0)[0] == 2
    count, reset_in = rate_limit.hit(rule, "1.2.3.4", now=179.0)
    assert (count, reset_in) == (3, 1)
    assert rate_limit.hit(rule, "1.2.3.4", now=181.0)[0] == 1
    assert rate_limit.hit(rule, "5.6.7.8", now=181.0)[0] == 1


def test_redis_counter_expires_its_window(fake_redis) -> None:
    rule = rate_limit.Rule("unit", 5)
    assert rate_limit.hit(rule, "9.9.9.9", now=60.0)[0] == 1
    assert rate_limit.hit(rule, "9.9.9.9", now=61.0)[0] == 2
    key = "gf:rl:unit:9.9.9.9:1"
    assert fake_redis.get(key) == "2"
    assert fake_redis.ttl(key) > 0


def test_sign_in_endpoints_answer_429_after_the_limit(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_auth_per_minute", 3)
    rate_limit.reset_local()
    try:
        # Body thiếu trường: 422 trước khi chạm database, nhưng vẫn bị đếm.
        codes = [client.post("/api/v1/auth/login", json={}).status_code for _ in range(4)]
        assert codes == [422, 422, 422, 429]
        blocked = client.post("/api/v1/auth/login", json={})
        assert blocked.json()["error"]["code"] == "RATE_LIMITED"
        assert int(blocked.headers["Retry-After"]) > 0
        assert blocked.headers["X-RateLimit-Limit"] == "3"
    finally:
        rate_limit.reset_local()


def test_responses_carry_security_headers_and_request_id() -> None:
    response = client.get("/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Request-ID"]


# --------------------------------------------------------------------------
# Exports, PDF, mail, logging
# --------------------------------------------------------------------------

COLUMNS = (
    Column("name", "Họ tên"),
    Column("amount", "Số tiền", "money"),
    Column("at", "Lúc", "datetime"),
    Column("count", "SL", "int"),
    Column("label", "Nhãn", value=lambda row: row["name"].upper()),
)
ROWS = [
    {
        "name": "Trần Thị Bé",
        "amount": Decimal("500000"),
        "at": datetime(2026, 10, 1, 3),
        "count": 2,
    },
    {"name": "Lê Văn C", "amount": None, "at": None, "count": None},
]


def test_csv_export_is_excel_friendly_utf8() -> None:
    content = exporters.to_csv(COLUMNS, ROWS)
    assert content.startswith("﻿".encode())
    lines = content.decode("utf-8-sig").splitlines()
    assert lines[0] == "Họ tên,Số tiền,Lúc,SL,Nhãn"
    # Giờ phòng tập (UTC+7) và số tiền dạng số thô.
    assert lines[1] == "Trần Thị Bé,500000,01/10/2026 10:00,2,TRẦN THỊ BÉ"
    assert lines[2] == "Lê Văn C,0,,,LÊ VĂN C"


def test_xlsx_export_keeps_numbers_and_dates_typed() -> None:
    workbook = load_workbook(io.BytesIO(exporters.to_xlsx("Báo cáo", "Lọc", COLUMNS, ROWS)))
    sheet = workbook.active
    assert sheet["A1"].value == "Báo cáo"
    assert [cell.value for cell in sheet[4]] == ["Họ tên", "Số tiền", "Lúc", "SL", "Nhãn"]
    assert sheet["B5"].value == 500000
    assert sheet["B5"].number_format == '#,##0 "đ"'
    assert sheet["C5"].value == datetime(2026, 10, 1, 10)
    assert sheet.freeze_panes == "A5"


def test_pdf_exports_are_real_pdfs() -> None:
    assert exporters.render("pdf", "Danh sách", "Lọc", COLUMNS, ROWS).startswith(b"%PDF-")
    assert exporters.render("pdf", "Trống", "Lọc", COLUMNS, []).startswith(b"%PDF-")
    invoice = pdf.InvoiceData(
        invoice_number="HD202610-00001",
        issued_at=datetime(2026, 10, 1, 10),
        payment_number="IRX261001ABCDEF12",
        status="Đã thanh toán",
        method="Tiền mặt",
        paid_at=None,
        customer_name="Nguyễn Văn A",
        customer_code=None,
        customer_email=None,
        customer_phone=None,
        branch_name="IRONIX",
        branch_address="",
        lines=[pdf.InvoiceLine("Gym theo tháng", 1, Decimal("500000"))],
        total=Decimal("500000"),
    )
    assert pdf.invoice_pdf(invoice).startswith(b"%PDF-")


def test_money_and_text_helpers() -> None:
    assert pdf.money(Decimal("1234567")) == "1.234.567 đ"
    assert pdf.money(None) == "0 đ"
    assert pdf.text("<b>&") == "&lt;b&gt;&amp;"


def test_mail_message_and_outbox(tmp_path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_root", str(tmp_path))
    monkeypatch.setattr(settings, "smtp_host", "")
    message = mailer.build_message(
        mailer.Mail(
            to="a@example.com",
            subject="Xin chào",
            text="Nội dung",
            html="<p>Nội dung</p>",
            attachments=[mailer.Attachment("x.pdf", "application/pdf", b"%PDF-1.4")],
        )
    )
    assert message["Subject"] == "Xin chào"
    assert [part.get_filename() for part in message.iter_attachments()] == ["x.pdf"]

    name = _REAL_DELIVER(message)
    saved = tmp_path / "outbox" / name
    assert saved.is_file()
    assert b"a@example.com" in saved.read_bytes()


def test_json_log_lines_carry_request_id_and_extras() -> None:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "Xin %s", ("chào",), None)
    record.user_id = "u-1"
    token = request_id_var.set("req-123")
    try:
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["message"] == "Xin chào"
    assert line["request_id"] == "req-123"
    assert line["user_id"] == "u-1"
    assert line["level"] == "INFO"
    assert line["ts"].endswith("Z")


# --------------------------------------------------------------------------
# Service helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "period", "start", "label"),
    [
        (date(2026, 10, 15), "WEEK", date(2026, 10, 12), "Tuần 12/10"),
        (date(2026, 10, 15), "MONTH", date(2026, 10, 1), "T10/2026"),
        (date(2026, 11, 15), "QUARTER", date(2026, 10, 1), "Q4/2026"),
        (date(2026, 11, 15), "YEAR", date(2026, 1, 1), "2026"),
    ],
)
def test_report_periods(day, period, start, label) -> None:
    assert admin_service._period_start(day, period) == start
    assert admin_service._label(start, period) == label


def test_period_shift_crosses_year_boundaries() -> None:
    assert admin_service._shift(date(2026, 1, 1), "MONTH", -1) == date(2025, 12, 1)
    assert admin_service._shift(date(2026, 10, 1), "QUARTER", 1) == date(2027, 1, 1)
    assert admin_service._shift(date(2026, 10, 12), "WEEK", -2) == date(2026, 9, 28)


def test_percent_change() -> None:
    assert admin_service._percent_change(150, 100) == 50.0
    assert admin_service._percent_change(5, 0) is None


def test_invoice_lines_split_plan_and_pt_sessions() -> None:
    row = {
        "amount": Decimal("4800000"),
        "purpose": "MEMBERSHIP",
        "plan_name": "Gym theo năm",
        "pt_quantity": 3,
        "pt_unit_price": Decimal("200000"),
    }
    lines = invoices_service._lines(row)
    assert [(line.description, line.quantity, line.total) for line in lines] == [
        ("Gói hội viên: Gym theo năm", 1, Decimal("4200000")),
        ("Buổi tập với huấn luyện viên (PT)", 3, Decimal("600000")),
    ]
    assert invoices_service.describe(row).startswith("Gói hội viên: Gym theo năm + 3 Buổi")
    only_pt = {**row, "purpose": "PT_CREDIT", "plan_name": None, "amount": Decimal("600000")}
    assert [line.total for line in invoices_service._lines(only_pt)] == [Decimal("600000")]


def test_import_headers_accept_vietnamese_and_english_names() -> None:
    assert shop_service._header_key("Tên sản phẩm") == "name"
    assert shop_service._header_key("Ton kho") == "stock_quantity"
    assert shop_service._header_key("Nhóm (GYM/YOGA)") == "activity_type"
    assert shop_service._header_key("Trạng thái (ACTIVE/DRAFT/INACTIVE)") == "status"
    assert shop_service._header_key("category_name") == "category_name"
    assert shop_service._header_key("Ghi chú") is None
    assert shop_service._header_key(None) is None


def test_import_template_round_trips() -> None:
    name, content_type, content = shop_service.import_template("xlsx")
    assert name.endswith(".xlsx") and "spreadsheet" in content_type
    rows = list(shop_service._rows_from_file(name, content))
    assert rows[0][1][:2] == ["SKU", "Tên sản phẩm"]
    assert len(rows) == 3
    name, _, content = shop_service.import_template("csv")
    assert list(shop_service._rows_from_file(name, content))[1][1][0] == "GYM-ROPE-01"


def test_import_rejects_unknown_file_types() -> None:
    with pytest.raises(Exception) as caught:
        list(shop_service._rows_from_file("data.txt", b"x"))
    assert caught.value.detail["error"]["code"] == "UNSUPPORTED_FILE"


def test_export_subtitle_lists_active_filters() -> None:
    subtitle = exports_service._subtitle(
        {"status": "PAID", "search": None, "inside_only": False},
        datetime(2026, 10, 1, 3, tzinfo=UTC),
    )
    assert subtitle == "Bộ lọc: status: PAID · Xuất lúc 01/10/2026 10:00 (GMT+7)"
    assert exports_service._subtitle({}, datetime(2026, 10, 1, tzinfo=UTC)).startswith(
        "Bộ lọc: tất cả"
    )


# --------------------------------------------------------------------------
# Job queue dispatch
# --------------------------------------------------------------------------


def _capture_submit(monkeypatch) -> list:
    from app.tasks import queue

    submitted: list = []
    monkeypatch.setattr(queue._executor, "submit", lambda fn, job_id: submitted.append(job_id))
    return submitted


def test_dispatch_prefers_redis_when_available(fake_redis, monkeypatch) -> None:
    from app.tasks import queue

    monkeypatch.setattr(get_settings(), "job_queue_mode", "auto")
    submitted = _capture_submit(monkeypatch)
    queue.dispatch("job-redis")
    assert fake_redis.lrange(queue.QUEUE_KEY, 0, -1) == ["job-redis"]
    assert submitted == []


def test_dispatch_falls_back_to_a_thread_without_redis(monkeypatch) -> None:
    from app.tasks import queue

    monkeypatch.setattr(get_settings(), "job_queue_mode", "auto")
    submitted = _capture_submit(monkeypatch)
    queue.dispatch("job-thread")
    assert submitted == ["job-thread"]


def test_redis_only_mode_leaves_the_job_for_the_worker(monkeypatch) -> None:
    from app.tasks import queue

    monkeypatch.setattr(get_settings(), "job_queue_mode", "redis")
    submitted = _capture_submit(monkeypatch)
    queue.dispatch("job-wait")
    assert submitted == []


def test_inline_mode_runs_immediately(monkeypatch) -> None:
    from app.tasks import queue

    monkeypatch.setattr(get_settings(), "job_queue_mode", "inline")
    ran: list[str] = []
    monkeypatch.setattr(queue, "run", ran.append)
    queue.dispatch("job-now")
    assert ran == ["job-now"]
