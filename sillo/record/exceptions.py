"""
sillo.record.exceptions — Database exception handlers for HTTP responses.

Converts Tortoise / database errors into proper HTTP error responses
that can be registered as exception handlers on a sillo app.
"""

from __future__ import annotations

from tortoise.exceptions import (
    DoesNotExist,
    IntegrityError,
    OperationalError,
    ValidationError,
)

from sillo.responses import json


async def handle_does_not_exist(ctx, exc: DoesNotExist):
    """Return a 404 HTTP response when a Tortoise ``.get()`` query fails.

    Catches ``DoesNotExist`` exceptions raised by Tortoise ORM when a
    query for a single record returns no results, converting the
    database-level error into a standard HTTP 404 JSON response.

    Args:
        ctx: The context for the request that raised.
        exc: The caught ``DoesNotExist`` exception instance.

    Returns:
        A JSON response with ``{"error": "Not Found", "detail": "<message>"}``
        and a 404 status code.
    """
    return json({"error": "Not Found", "detail": str(exc)}, status_code=404)


async def handle_integrity_error(ctx, exc: IntegrityError):
    """Return a 409 Conflict response on unique-constraint or FK violations.

    Converts Tortoise ``IntegrityError`` exceptions (raised on duplicate
    key, null constraint, or foreign-key violations) into an HTTP 409
    JSON response.

    Args:
        ctx: The context for the request that raised.
        exc: The caught ``IntegrityError`` exception instance.

    Returns:
        A JSON response with ``{"error": "Conflict", "detail": "<message>"}``
        and a 409 status code.
    """
    return json({"error": "Conflict", "detail": str(exc)}, status_code=409)


async def handle_validation_error(ctx, exc: ValidationError):
    """Return a 422 Unprocessable Entity response on model validation failure.

    Catches Tortoise ``ValidationError`` (field-level validation failures
    such as type mismatches or out-of-range values) and returns a standard
    HTTP 422 JSON payload.

    Args:
        ctx: The context for the request that raised.
        exc: The caught ``ValidationError`` exception instance.

    Returns:
        A JSON response with ``{"error": "Validation Error", "detail": "<message>"}``
        and a 422 status code.
    """
    return json({"error": "Validation Error", "detail": str(exc)}, status_code=422)


async def handle_operational_error(ctx, exc: OperationalError):
    """Return a 503 Service Unavailable when the database is unreachable.

    Converts Tortoise ``OperationalError`` exceptions (connection refused,
    server timeout, network partition) into an HTTP 503 JSON response so
    upstream load-balancers or monitoring can react appropriately.

    Args:
        ctx: The context for the request that raised.
        exc: The caught ``OperationalError`` exception instance.

    Returns:
        A JSON response with ``{"error": "Service Unavailable", "detail": "..."}``
        and a 503 status code.
    """
    return json(
        {"error": "Service Unavailable", "detail": "Database unavailable"},
        status_code=503,
    )


def register_db_exception_handlers(app) -> None:
    """Register all database exception handlers on *app*.

    Call once during application setup::

        app = SilloApp()
        register_db_exception_handlers(app)
    """
    app.add_exception_handler(DoesNotExist, handle_does_not_exist)
    app.add_exception_handler(IntegrityError, handle_integrity_error)
    app.add_exception_handler(ValidationError, handle_validation_error)
    app.add_exception_handler(OperationalError, handle_operational_error)
