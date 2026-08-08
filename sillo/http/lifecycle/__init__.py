"""Lifecycle management package for request-scoped context and request ID tracking.

This package provides middleware, helpers, and context utilities for managing
request lifecycles in the Sillo framework. It includes automatic request ID
generation and propagation, request-scoped state management via context
variables, and configurable middleware for integrating these capabilities
into the request/response pipeline.

Public API:
    RequestIdMiddleware, RequestId, RequestContext, and various helper
    functions for request ID generation, validation, and storage.
"""

from .context import RequestContext
from .helpers import (
    generate_request_id,
    get_or_generate_request_id,
    get_request_id_from_header,
    get_request_id_from_request,
    set_request_id_header,
    store_request_id_in_request,
    validate_request_id,
)
from .middleware import RequestId, RequestIdMiddleware

__all__ = [
    "RequestContext",
    "RequestId",
    "RequestIdMiddleware",
    "generate_request_id",
    "get_or_generate_request_id",
    "get_request_id_from_header",
    "get_request_id_from_request",
    "set_request_id_header",
    "store_request_id_in_request",
    "validate_request_id",
]
