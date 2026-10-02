"""Application error types and FastAPI exception handlers.

All errors return a consistent envelope: {"error": {"code": "...", "message": "..."}}.
Service code raises these typed exceptions; handlers map them to HTTP responses.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger("app.errors")


class AppError(Exception):
    """Base class for application errors mapped to an HTTP status + code."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class SlotUnavailableError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "SLOT_UNAVAILABLE"
    message = "This slot is already booked for the selected date."


class ItemInvalidError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "ITEM_INVALID"
    message = "One or more selected items are not valid for this location or date."


class BookingDateInPastError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "BOOKING_DATE_IN_PAST"
    message = "The booking date cannot be in the past."


class AcceptRequiresAdvanceError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "ACCEPT_REQUIRES_ADVANCE"
    message = "Recorded payments are below the required advance for this plan."


class ValidationFailedError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"
    message = "The request failed validation."


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_CREDENTIALS"
    message = "Invalid username or password."


class UnauthenticatedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHENTICATED"
    message = "Authentication is required."


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


class LocationAccessDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "LOCATION_ACCESS_DENIED"
    message = "You do not have access to this location."


class OriginNotAllowedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "ORIGIN_NOT_ALLOWED"
    message = "Request origin is not allowed."


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "The requested resource was not found."


def _envelope(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that render the consistent error envelope."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_envelope(exc.code, exc.message)
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("VALIDATION_ERROR", "The request failed validation."),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Log the traceback without PII; return a generic 500.
        log.error("unhandled_exception", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
        )
