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
from app.db.session import engine

settings = get_settings()


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
    yield
    engine.dispose()


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

    @application.middleware("http")
    async def attach_request_id(request: Request, call_next):
        supplied_id = request.headers.get("X-Request-ID", "").strip()
        request_id = supplied_id if 0 < len(supplied_id) <= 128 else str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
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
