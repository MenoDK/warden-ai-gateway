"""Application factory."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from ai_core import __version__
from ai_core.api.routes import router
from ai_core.config import Settings, get_settings
from ai_core.container import Container, build_container
from ai_core.errors import AppError
from ai_core.gateway.router import GatewayError, NoEligibleProvider
from ai_core.observability.logging import configure_logging, request_id_var

log = logging.getLogger("ai_core")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def create_app(settings: Settings | None = None, *, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await container.startup()
        try:
            yield
        finally:
            await container.shutdown()

    app = FastAPI(title="AI Core", version=__version__, lifespan=lifespan)
    app.state.container = container
    app.include_router(router)

    @app.middleware("http")
    async def observe(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = rid
            response.headers["x-content-type-options"] = "nosniff"
            response.headers["cache-control"] = "no-store"
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = getattr(request.scope.get("route"), "path", "unmatched")
            container.metrics.http_requests.labels(request.method, route, str(status)).inc()
            container.metrics.http_latency.labels(request.method, route).observe(elapsed)
            if route not in ("/health/live", "/metrics"):
                log.info(
                    "request",
                    extra={
                        "extra_fields": {
                            "method": request.method,
                            "route": route,
                            "status": status,
                            "ms": round(elapsed * 1000, 1),
                        }
                    },
                )
            request_id_var.reset(token)

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": request_id_var.get(),
                    **({"details": exc.details} if exc.details else {}),
                }
            },
            status_code=exc.status_code,
        )

    @app.exception_handler(GatewayError)
    async def gateway_error(_: Request, exc: GatewayError) -> JSONResponse:
        code = "no_eligible_provider" if isinstance(exc, NoEligibleProvider) else "all_providers_failed"
        return JSONResponse(
            {
                "error": {
                    "code": code,
                    "message": str(exc),
                    "request_id": request_id_var.get(),
                    "attempts": [{"provider": a.provider, "outcome": a.outcome} for a in exc.attempts],
                }
            },
            status_code=503,
        )

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=exc)
        return JSONResponse(
            {"error": {"code": "internal_error", "message": "internal error", "request_id": request_id_var.get()}},
            status_code=500,
        )

    return app


def app_factory() -> FastAPI:  # uvicorn --factory ai_core.main:app_factory
    return create_app()
