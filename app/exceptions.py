"""Domain exceptions + the handlers that turn them into a consistent JSON error shape.

Every error the API returns looks like:
    {"error": {"code": "not_found", "message": "Recipe not found", "details": null}}
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("feastfit")


class AppError(Exception):
    """Base class for all expected, client-facing errors."""

    status_code = 500
    code = "internal_error"
    message = "Something went wrong"

    def __init__(self, message: str | None = None, *, details=None, headers: dict | None = None):
        self.message = message or self.message
        self.details = details
        self.headers = headers
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Resource already exists"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_failed"
    message = "Not authenticated"

    def __init__(self, message: str | None = None, *, details=None):
        super().__init__(message, details=details, headers={"WWW-Authenticate": "Bearer"})


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to do that"


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Invalid input"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"
    message = "File is too large"


class UnsupportedMediaError(AppError):
    status_code = 415
    code = "unsupported_media_type"
    message = "Unsupported file type"


_HTTP_CODES = {
    400: "bad_request",
    401: "authentication_failed",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
}


def error_body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"][1:]) or str(err["loc"][0]),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Request validation failed", details),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError):
        logger.warning("Integrity error: %s", exc.orig)
        return JSONResponse(
            status_code=409,
            content=error_body("conflict", "That change conflicts with existing data"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = str(exc.detail)
        if not request.url.path.startswith("/api") and request.method == "GET":
            from app.templating import templates

            return templates.TemplateResponse(
                request,
                "error.html",
                {"status": exc.status_code, "message": message},
                status_code=exc.status_code,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception):
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "An unexpected error occurred"),
        )
