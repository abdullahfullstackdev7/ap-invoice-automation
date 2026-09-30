import uuid

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

PROBLEM_JSON = "application/problem+json"


def _problem(
    status_code: int, title: str, detail: str | None = None, request_id: str | None = None
) -> JSONResponse:
    body = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
    }
    if detail is not None:
        body["detail"] = detail
    if request_id is not None:
        body["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_JSON)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return _problem(exc.status_code, title=exc.detail, request_id=request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return _problem(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation error",
            detail=str(exc.errors()),
            request_id=request_id,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error("unhandled_exception", request_id=request_id, error=str(exc))
        return _problem(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal server error",
            request_id=request_id,
        )
