"""Uniform API errors: {"error": {"code", "message", "details"}}."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnsupportedImageError(AppError):
    status_code = 415
    code = "unsupported_image"


class InvalidImageError(AppError):
    status_code = 422
    code = "invalid_image"


class ImageTooLargeError(AppError):
    status_code = 413
    code = "image_too_large"


def _body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(
            _body("validation_error", "Request validation failed.", {"errors": errors}),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        import logging

        logging.getLogger("pharmasource").exception("unhandled error: %s", type(exc).__name__)
        return JSONResponse(_body("internal_error", "Unexpected server error."), status_code=500)
