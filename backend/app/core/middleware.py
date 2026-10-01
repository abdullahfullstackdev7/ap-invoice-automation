import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.settings import get_settings

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects request bodies above a coarse cap before they reach a route.

    This is a cheap, early DoS guard based on Content-Length, sized to
    allow a multi-file upload (up to MAX_FILES_PER_UPLOAD files at
    MAX_UPLOAD_MB each). The upload route validates each file's actual
    size against MAX_UPLOAD_MB individually; this middleware is not the
    source of truth for the per-file limit.
    """

    MAX_FILES_PER_UPLOAD = 20

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        max_bytes = settings.max_upload_mb * self.MAX_FILES_PER_UPLOAD * 1024 * 1024
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > max_bytes:
            return JSONResponse(
                status_code=413,
                content={"type": "about:blank", "title": "Request body too large", "status": 413},
                media_type="application/problem+json",
            )
        return await call_next(request)
