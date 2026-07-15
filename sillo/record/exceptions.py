"""
sillo.record.exceptions — Database exception handlers for HTTP responses.

Converts Tortoise / database errors into proper HTTP error responses
that can be registered as exception handlers on a sillo app.
"""

from __future__ import annotations

from typing import Annotated

from tortoise.exceptions import (
    DoesNotExist,
    IntegrityError,
    OperationalError,
    ValidationError,
)
from typing_extensions import Doc


async def handle_does_not_exist(request, response, exc: DoesNotExist):
    """Return 404 when a Tortoise .get() fails."""
    return response.json({"error": "Not Found", "detail": str(exc)}, status_code=404)


async def handle_integrity_error(request, response, exc: IntegrityError):
    """Return 409 when a unique constraint or FK is violated."""
    return response.json({"error": "Conflict", "detail": str(exc)}, status_code=409)


async def handle_validation_error(request, response, exc: ValidationError):
    """Return 422 when model validation fails."""
    return response.json(
        {"error": "Validation Error", "detail": str(exc)}, status_code=422
    )


async def handle_operational_error(request, response, exc: OperationalError):
    """Return 503 when the database is unreachable."""
    return response.json(
        {"error": "Service Unavailable", "detail": "Database unavailable"},
        status_code=503,
    )


def register_db_exception_handlers(app) -> None:
    """Register all database exception handlers on *app*.

    Call once during application setup::

        app = silloApp()
        register_db_exception_handlers(app)
    """
    app.add_exception_handler(DoesNotExist, handle_does_not_exist)
    app.add_exception_handler(IntegrityError, handle_integrity_error)
    app.add_exception_handler(ValidationError, handle_validation_error)
    app.add_exception_handler(OperationalError, handle_operational_error)
