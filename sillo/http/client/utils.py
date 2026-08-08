from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from typing import Any

    from httpx import Response as HttpxResponse


def extract_response_summary(response: HttpxResponse) -> dict[str, Any]:
    """Extract a human-readable summary from an httpx response.

    Returns a dict with status_code, url, method, elapsed, headers,
    body_preview, and content_length.
    """
    body = response.text
    return {
        "status_code": response.status_code,
        "url": str(response.url),
        "method": response.request.method if response.request else "UNKNOWN",
        "elapsed": response.elapsed.total_seconds(),
        "headers": dict(response.headers),
        "body_preview": body[:500] if body else None,
        "content_length": len(body),
    }


def merge_headers(
    base: dict[str, str] | None,
    override: dict[str, str] | None,
) -> dict[str, str]:
    """Merge two header dicts, with override taking precedence."""
    result: dict[str, str] = {}
    if base:
        result.update(base)
    if override:
        result.update(override)
    return result


def sanitize_url_for_log(url: str) -> str:
    """Remove sensitive query parameters from a URL for logging.

    Strips common sensitive query params like api_key, token,
    secret, password, and key.
    """
    import re

    sensitive_params = {
        "api_key",
        "token",
        "secret",
        "password",
        "key",
        "apikey",
        "access_token",
    }
    return re.sub(
        r"([?&])(" + "|".join(sensitive_params) + r")=[^&]+",
        r"\1\2=***",
        url,
        flags=re.IGNORECASE,
    )


def guess_content_type(body: Any) -> str:
    """Guess the content type for a request body."""
    if isinstance(body, (dict, list)):
        return "application/json"
    if isinstance(body, str):
        return "text/plain"
    if isinstance(body, bytes):
        return "application/octet-stream"
    if hasattr(body, "read"):
        return "application/octet-stream"
    return "application/json"


__all__ = [
    "extract_response_summary",
    "guess_content_type",
    "merge_headers",
    "sanitize_url_for_log",
]
