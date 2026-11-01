"""Domain errors. Each carries a stable machine-readable code and an HTTP status."""

from __future__ import annotations


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class BadRequest(AppError):
    status_code = 400
    code = "bad_request"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class SourceNotAllowed(AppError):
    status_code = 422
    code = "source_not_allowed"


class PayloadTooLarge(AppError):
    status_code = 413
    code = "payload_too_large"


class InvalidState(AppError):
    status_code = 409
    code = "invalid_state"


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"
