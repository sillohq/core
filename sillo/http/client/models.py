from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from httpx import Response as HttpxResponse
from pydantic import BaseModel


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
    ttl: Optional[int] = None

    @classmethod
    def from_httpx_response(
        cls,
        response: HttpxResponse,
        ttl: Optional[int] = None,
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


class ResponseValidator:
    """Validates and deserializes HTTP response bodies using Pydantic models."""

    @staticmethod
    def validate(
        response_body: str,
        response_model: Optional[type[BaseModel]] = None,
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
                return [response_model.model_validate(item, strict=strict) for item in data]
            return response_model.model_validate(data, strict=strict)
        except ValidationError as exc:
            raise HTTPValidationError(
                f"Response validation failed: {exc}",
                validation_errors=exc.errors(),
                response_body=response_body,
            ) from exc


CachedResponse.model_rebuild()

__all__ = [
    "CachedResponse",
    "ResponseValidator",
]
