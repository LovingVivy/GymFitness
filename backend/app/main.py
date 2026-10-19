import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_var
from app.core.rate_limit import client_ip, rate_limit_middleware
from app.db.session import SessionLocal, engine
from app.services import admin as admin_service
from app.tasks import maintenance

settings = get_settings()
configure_logging(settings.log_level, settings.json_logs)
logger = logging.getLogger(__name__)
access_logger = logging.getLogger("app.access")

# Header bảo mật mặc định; route nào tự đặt (vd. /files có CSP riêng) thì giữ nguyên.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _serializable_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Make Pydantic error entries JSON-safe.

    A ``field_validator`` that raises ``ValueError`` leaves the exception object
    inside ``ctx``, which ``json.dumps`` cannot encode and would turn a 422 into
    a 500.
    """
    safe: list[dict[str, Any]] = []
    for error in errors:
        item = {key: value for key, value in error.items() if key != "ctx"}
        context = error.get("ctx")
        if isinstance(context, dict):
            item["ctx"] = {key: str(value) for key, value in context.items()}
        safe.append(item)
    return safe


@asynccontextmanager
async def lifespan(_: FastAPI):
    _bootstrap_admin()
    maintenance.start_background()
    yield
    maintenance.stop_background()
    engine.dispose()


def _bootstrap_admin() -> None:
    """Tạo tài khoản admin mặc định; lỗi database không được chặn API khởi động."""
    try:
        with SessionLocal() as db:
            admin_service.ensure_default_admin(db)
    except Exception:  # pragma: no cover - phụ thuộc môi trường
        logger.exception("Không tạo được tài khoản admin mặc định.")


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Thứ tự: middleware khai báo sau chạy trước. Request id + access log bọc ngoài
    # cùng để cả request bị rate limit (429) cũng có log.
    application.middleware("http")(rate_limit_middleware)

    @application.middleware("http")
    async def attach_request_id(request: Request, call_next):
        supplied_id = request.headers.get("X-Request-ID", "").strip()
        request_id = supplied_id if 0 < len(supplied_id) <= 128 else str(uuid4())
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            path = request.url.path
            level = logging.DEBUG if path.startswith("/health") else logging.INFO
            access_logger.log(
                level,
                "%s %s %s",
                request.method,
                path,
                status_code,
                extra={
                    "method": request.method,
                    "path": path,
                    "status": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip(request),
                    "user_id": getattr(request.state, "user_id", None),
                },
            )
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Emit the documented error envelope: ``{"error": {...}}``.

        Handlers that already raise ``{"error": {...}}`` as their detail keep
        that shape at the top level; anything else falls back to ``detail``.
        """
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            content: dict[str, Any] = detail
        else:
            content = {"detail": detail}
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        messages = []
        for error in exc.errors():
            loc = [
                str(part) for part in error.get("loc", []) if part not in ("body", "query", "path")
            ]
            field = ".".join(loc) or "request"
            messages.append(f"{field}: {error.get('msg', 'invalid')}")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "; ".join(messages),
                    "details": _serializable_errors(exc.errors()),
                }
            },
        )

    application.include_router(api_router)
    return application


app = create_app()
