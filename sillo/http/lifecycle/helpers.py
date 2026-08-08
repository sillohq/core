from __future__ import annotations

import uuid

from sillo.core.http import Request, Response


def generate_request_id() -> str:
    """Generate a new universally unique identifier for request tracking.

    Creates a random UUID4 string suitable for use as a request
    identifier. Each call produces a distinct value with negligible
    collision probability, making it safe for high-throughput
    concurrent request handling.

    Args:
        None.

    Returns:
        str: A lowercase hyphenated UUID4 string (e.g.
            ``"550e8400-e29b-41d4-a716-446655440000"``).

    Raises:
        None.
    """
    return str(uuid.uuid4())


def get_request_id_from_header(
    request: Request, header_name: str = "X-Request-ID"
) -> str | None:
    """Extract a request ID from an incoming HTTP request header.

    Reads the value of the specified header from the request's header
    map. Returns ``None`` when the header is absent, allowing callers
    to decide whether to generate a new ID or reject the request.

    Args:
        request (Request): The incoming HTTP request object whose
            headers should be inspected.
        header_name (str, optional): The case-sensitive header name
            to look up. Defaults to ``"X-Request-ID"``.

    Returns:
        Optional[str]: The header value as a string if present, or
            ``None`` if the header does not exist on the request.

    Raises:
        None.
    """
    return request.headers.get(header_name)


def set_request_id_header(
    response: Response, request_id: str, header_name: str = "X-Request-ID"
) -> None:
    """Attach a request ID header to an outgoing HTTP response.

    Sets the specified header on the response object, overwriting any
    existing value. This ensures the client receives the canonical
    request ID used for tracing and log correlation.

    Args:
        response (Response): The outgoing HTTP response object on
            which to set the header.
        request_id (str): The request identifier value to write into
            the response header.
        header_name (str, optional): The header name to use. Defaults
            to ``"X-Request-ID"``.

    Returns:
        None.

    Raises:
        None.
    """
    response.set_header(header_name, request_id, overide=True)


def get_or_generate_request_id(
    request: Request, header_name: str = "X-Request-ID"
) -> str:
    """Return an existing request ID from headers or generate a new one.

    First attempts to extract the request ID from the incoming request
    header. If the header is missing or empty, a fresh UUID4 is
    generated instead. This guarantees a non-empty request ID is
    always available for downstream processing.

    Args:
        request (Request): The incoming HTTP request object to
            inspect for an existing request ID header.
        header_name (str, optional): The header name to check.
            Defaults to ``"X-Request-ID"``.

    Returns:
        str: The request ID, either extracted from the header or
            newly generated as a UUID4 string.

    Raises:
        None.
    """
    request_id = get_request_id_from_header(request, header_name)
    if not request_id:
        request_id = generate_request_id()
    return request_id


def validate_request_id(request_id: str) -> bool:
    """Validate that a string conforms to the UUID format.

    Attempts to parse the given string as a UUID. Returns ``True`` if
    parsing succeeds, indicating the string is a well-formed UUID
    (any version). Returns ``False`` for malformed strings, empty
    values, or non-string types.

    Args:
        request_id (str): The candidate string to validate as a
            UUID-formatted request identifier.

    Returns:
        bool: ``True`` if ``request_id`` is a valid UUID string,
            ``False`` otherwise.

    Raises:
        None.
    """
    try:
        uuid.UUID(request_id)
        return True
    except (ValueError, TypeError):
        return False


def store_request_id_in_request(
    request: Request, request_id: str, attribute_name: str = "request_id"
) -> None:
    """Persist a request ID onto the request's mutable state object.

    Writes the request ID into ``request.state`` under the given
    attribute name, making it accessible to downstream handlers and
    middleware without re-parsing headers.

    Args:
        request (Request): The HTTP request object whose state
            should be updated with the request ID.
        request_id (str): The request identifier value to store.
        attribute_name (str, optional): The attribute name to use on
            ``request.state``. Defaults to ``"request_id"``.

    Returns:
        None.

    Raises:
        None.
    """
    request.state.update({attribute_name: request_id})


def get_request_id_from_request(
    request: Request, attribute_name: str = "request_id"
) -> str | None:
    """Retrieve a previously stored request ID from the request state.

    Reads the request ID from ``request.state`` using the given
    attribute name. Returns ``None`` if the attribute was never set,
    indicating that ``store_request_id_in_request`` was not called
    earlier in the request pipeline.

    Args:
        request (Request): The HTTP request object to read the
            stored request ID from.
        attribute_name (str, optional): The attribute name to look
            up on ``request.state``. Defaults to ``"request_id"``.

    Returns:
        Optional[str]: The stored request ID string, or ``None`` if
            the attribute is not present on the request state.

    Raises:
        None.
    """
    return getattr(request.state, attribute_name, None)
