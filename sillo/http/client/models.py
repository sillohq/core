from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar, cast

from httpx import Response as HttpxResponse
from pydantic import BaseModel

T = TypeVar("T")


class CachedResponse(BaseModel):
    """A serialisable representation of a cached HTTP response.

    Stored in the cache backend instead of the raw httpx.Response,
    which cannot be serialized. Includes enough metadata to reconstruct
    the response information without re-hitting the upstream server.
    """

    status_code: int
    headers: dict[str, str]
    body: str
    url: str
    method: str
    cached_at: datetime
    ttl: int | None = None

    @classmethod
    def from_httpx_response(
        cls,
        response: HttpxResponse,
        ttl: int | None = None,
    ) -> CachedResponse:
        """Build a CachedResponse from an httpx response."""
        return cls(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.text,
            url=str(response.url),
            method=response.request.method if response.request else "UNKNOWN",
            cached_at=datetime.now(),
            ttl=ttl,
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for cache storage."""
        return self.model_dump(mode="json")

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> CachedResponse:
        """Reconstruct from a JSON-compatible dict retrieved from cache."""
        return cls.model_validate(data)


class ClientResponse(Generic[T]):
    """An HTTP response whose body is decoded exactly as before.

    :meth:`HTTPClient.request` returns the decoded body and nothing else, so a
    caller cannot see the status code or headers of a response it already has
    in hand. That makes the common integrations impossible to build against
    this client -- a webhook sender has to classify the delivery by status and
    read ``Retry-After``; a webhook receiver has to read the signature header
    the sender wrote; a paged collection is only reachable through the ``Link``
    header.

    Passing ``with_response=True`` returns one of these instead. ``body`` holds
    precisely what the call would have returned without the flag -- the parsed
    JSON, the raw text, or the validated model -- so opting in changes what is
    wrapped, never how the body is decoded.

    Usage:
        ```python
        async with HTTPClient("https://api.example.com") as client:
            res = await client.post("/hooks", json=payload, with_response=True)
            if res.is_success:
                log(res.status_code, res.headers.get("retry-after"))
        ```

    The underlying :class:`httpx.Response` is available as ``raw`` for anything
    this does not surface. Reading a header is why this exists, so ``headers``
    is a plain ``dict`` and works with ``.get()`` without importing httpx.
    """

    __slots__ = ("_body", "_raw", "headers", "status_code", "url")

    def __init__(
        self,
        status_code: int,
        headers: dict[str, str],
        body: T,
        url: str,
        raw: HttpxResponse | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers
        self.url = url
        self._body = body
        self._raw = raw

    @property
    def body(self) -> T:
        """The decoded body -- identical to this call's return without the flag."""
        return self._body

    @property
    def raw(self) -> HttpxResponse | None:
        """The underlying httpx response, for metadata not surfaced here."""
        return self._raw

    @property
    def is_success(self) -> bool:
        """Whether the status code is 2xx."""
        return 200 <= self.status_code < 300

    @property
    def is_error(self) -> bool:
        """Whether the status code is 4xx or 5xx."""
        return self.status_code >= 400

    def json(self) -> Any:
        """The body as JSON, whether or not a ``response_model`` was used.

        A body already validated into a model is dumped back to plain JSON
        rather than re-parsed, which is the same content the caller received.
        A body that is not JSON at all -- a plain-text or HTML error page --
        raises :class:`~sillo.http.client.errors.HTTPDecodeError`, the error
        the client already raises for an undecodable body, rather than the
        ``json.JSONDecodeError`` that decoding one would otherwise surface.
        """
        if isinstance(self._body, (dict, list, int, float, bool)):
            return self._body
        if isinstance(self._body, BaseModel):
            return self._body.model_dump(mode="json")

        import json as _json

        from sillo.http.client.errors import HTTPDecodeError

        try:
            # The body is a str here: _send decodes text, and the JSON-shaped
            # and model cases are already handled above. `body` is typed as an
            # unconstrained T, so narrow it for the checker.
            return _json.loads(cast("str | bytes | bytearray", self._body))
        except (TypeError, ValueError) as exc:
            raise HTTPDecodeError(f"Response body is not valid JSON: {exc}") from exc

    def __repr__(self) -> str:
        return (
            f"ClientResponse(status_code={self.status_code}, url={self.url!r}, "
            f"body={self._body!r})"
        )


class ResponseValidator:
    """Validates and deserializes HTTP response bodies using Pydantic models."""

    @staticmethod
    def validate(
        response_body: str,
        response_model: type[BaseModel] | None = None,
        *,
        many: bool = False,
        strict: bool = False,
    ) -> Any:
        """Validate a response body against an optional Pydantic model.

        Args:
            response_body: The raw JSON response body string.
            response_model: A Pydantic BaseModel subclass to validate against.
                When ``None``, the raw parsed JSON is returned.
            many: When ``True``, expects a JSON array and validates each element.
            strict: When ``True``, enables Pydantic strict mode validation.

        Returns:
            The validated Pydantic model instance, a list of model instances,
            or the raw parsed JSON when no model is provided.

        Raises:
            HTTPDecodeError: If the body is not valid JSON.
            HTTPValidationError: If validation against the model fails.
        """
        import json

        from pydantic import ValidationError

        from sillo.http.client.errors import HTTPDecodeError, HTTPValidationError

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise HTTPDecodeError(f"Response body is not valid JSON: {exc}") from exc

        if response_model is None:
            return data

        try:
            if many:
                if not isinstance(data, list):
                    raise HTTPValidationError(
                        "Expected a JSON array but got a non-list value",
                        validation_errors=[],
                        response_body=response_body,
                    )
                return [
                    response_model.model_validate(item, strict=strict) for item in data
                ]
            return response_model.model_validate(data, strict=strict)
        except ValidationError as exc:
            raise HTTPValidationError(
                f"Response validation failed: {exc}",
                validation_errors=exc.errors(),  # ty: ignore[invalid-argument-type]
                response_body=response_body,
            ) from exc


CachedResponse.model_rebuild()

__all__ = [
    "CachedResponse",
    "ClientResponse",
    "ResponseValidator",
]
