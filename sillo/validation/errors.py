from __future__ import annotations

from typing import Any, Dict, List, Sequence

from pydantic import ValidationError

__all__ = [
    "RequestValidationError",
    "ResponseValidationError",
    "prefix_errors",
]


def prefix_errors(
    exc: ValidationError,
    location: str,
    *,
    alias_map: Dict[str, str] | None = None,
) -> List[Dict[str, Any]]:
    """Convert a Pydantic ValidationError into location-prefixed error dicts.

    Pydantic reports ``loc`` tuples relative to the model it validated, which
    for sillo is a synthetic per-location model. A field failure therefore
    arrives as ``("page",)`` with no indication of *where* ``page`` came from.
    This prepends the request location so clients can tell a bad query string
    from a bad JSON body, producing ``("query", "page")``.

    Field names in the synthetic models are Python identifiers, which may
    differ from the wire name when an alias is in play. ``alias_map`` restores
    the wire name so the reported path matches what the client actually sent.

    Args:
        exc: The Pydantic ``ValidationError`` raised while validating one
            location's synthetic model.
        location: The request location the model represents, such as
            ``"query"``, ``"body"``, ``"path"``, ``"header"``, ``"cookie"``,
            or ``"form"``.
        alias_map: Optional mapping of Python field name to wire name. When a
            leading ``loc`` element matches a key, it is replaced by the alias.

    Returns:
        A list of error dictionaries mirroring ``exc.errors()`` but with
        ``loc`` converted to a list whose first element is ``location``, and
        with the ``url`` key stripped (it points at pydantic.dev docs and is
        noise in an HTTP API response).
    """
    out: List[Dict[str, Any]] = []
    for err in exc.errors():
        loc: Sequence[Any] = err.get("loc", ())
        if alias_map and loc and loc[0] in alias_map:
            loc = (alias_map[loc[0]], *loc[1:])
        item = {
            "loc": [location, *loc],
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        if "input" in err:
            item["input"] = err["input"]
        out.append(item)
    return out


class RequestValidationError(Exception):
    """Raised when client-supplied request data fails validation.

    Carries a flat list of already location-prefixed error dictionaries so the
    exception handler can serialize them without re-deriving where each failure
    came from. A single request can accumulate failures from several locations
    at once (for example a bad query parameter *and* a malformed body), which
    is why the errors are a flat list rather than one wrapped
    ``ValidationError``.

    This maps to HTTP 422 Unprocessable Entity: the request was well-formed
    enough to route, but its contents did not satisfy the declared schema.

    Attributes:
        errors: The list of error dictionaries, each with ``loc``, ``msg``,
            and ``type`` keys as produced by ``prefix_errors``.
        body: The raw request payload that failed validation, when available.
            Useful for debugging and for handlers that want to echo it back.
    """

    def __init__(
        self, errors: List[Dict[str, Any]], *, body: Any = None
    ) -> None:
        """Initialize the error with prefixed error dicts and optional payload.

        Args:
            errors: Location-prefixed error dictionaries, typically the
                concatenation of one or more ``prefix_errors`` results.
            body: The raw request payload that failed validation. Defaults to
                ``None`` when the payload is unavailable or not meaningful.
        """
        self.errors = errors
        self.body = body
        super().__init__(f"{len(errors)} validation error(s) in request")


class ResponseValidationError(Exception):
    """Raised when a handler's return value fails its declared response_model.

    Unlike ``RequestValidationError`` this is **not** a client error. The
    client sent a valid request; the application produced a response that does
    not match the contract it published. That is a server-side bug, so it maps
    to HTTP 500 rather than 422 — returning 422 here would wrongly blame the
    caller and would corrupt API semantics for clients retrying on 4xx.

    Attributes:
        errors: Error dictionaries prefixed with the ``"response"`` location.
        body: The offending value the handler returned.
    """

    def __init__(
        self, errors: List[Dict[str, Any]], *, body: Any = None
    ) -> None:
        """Initialize the error with prefixed error dicts and the bad value.

        Args:
            errors: Location-prefixed error dictionaries describing how the
                handler's return value violated the response model.
            body: The value the handler actually returned. Defaults to ``None``.
        """
        self.errors = errors
        self.body = body
        super().__init__(f"{len(errors)} validation error(s) in response")
