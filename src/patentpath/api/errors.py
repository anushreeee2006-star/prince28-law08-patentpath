"""RFC 9457 problem details error handling."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def get_request_id(request: Request) -> str | None:
    """Get the request ID assigned by middleware."""
    return getattr(request.state, "request_id", None)


def problem_response(
    request: Request,
    status: int,
    title: str,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Create an RFC 9457 problem details response."""

    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
    }

    request_id = get_request_id(request)
    if request_id:
        body["request_id"] = request_id

    if extra:
        body.update(extra)

    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle HTTP exceptions."""
    title = {
        404: "Not Found",
        401: "Unauthorized",
        403: "Forbidden",
    }.get(exc.status_code, "HTTP Error")

    return problem_response(
        request,
        exc.status_code,
        title,
        str(exc.detail),
        extra={"request_id": get_request_id(request)},
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle request validation errors."""

    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
        }
        for error in exc.errors()
    ]

    return problem_response(
        request,
        422,
        "Unprocessable Entity",
        "Request validation failed.",
        extra={"errors": errors},
    )
