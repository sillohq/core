from __future__ import annotations

import re
from base64 import b64encode
from collections.abc import Iterable
from hashlib import sha1
from typing import Any

from sillo.core.http import HttpContext
from sillo.core.http.response import BaseResponse
from sillo.middleware.base import BaseMiddleware

_WEAK_PREFIX = "W/"
_ETAG_TOKEN_RE = re.compile(r'^(W/)?\s*"[^"]*"\s*$')


def generate_etag_from_bytes(data: bytes, weak: bool = True) -> str:
    h = sha1()
    h.update(data)
    tag = f'"{b64encode(h.digest()).decode("utf-8")}"'
    return f"{_WEAK_PREFIX}{tag}" if weak else tag


def normalize_etag(tag: str) -> str:
    tag = tag.strip()
    if not _ETAG_TOKEN_RE.match(tag):
        if not tag.startswith(_WEAK_PREFIX):
            tag = f'"{tag.strip(chr(34))}"'
        else:
            tag = f'{_WEAK_PREFIX}"{tag[2:].strip().strip(chr(34))}"'
    if not _ETAG_TOKEN_RE.match(tag):
        raise ValueError(f"Invalid ETag token: {tag}")
    return tag


def set_response_etag(response: BaseResponse, etag: str, override: bool = True) -> None:
    response.set_header("etag", normalize_etag(etag), override=override)


def compute_and_set_etag(
    response: BaseResponse, body: bytes = b"", weak: bool = True, override: bool = False
) -> str:
    tag = generate_etag_from_bytes(body, weak=weak)
    set_response_etag(response, tag, override=override)
    return tag


def parse_if_none_match(ctx: HttpContext) -> list[str]:
    return _parse_etag_list(ctx.headers.get("if-none-match"))


def parse_if_match(ctx: HttpContext) -> list[str]:
    return _parse_etag_list(ctx.headers.get("if-match"))


def _parse_etag_list(value: str | None) -> list[str]:
    if not value:
        return []
    tags: list[str] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            tags.append(normalize_etag(part))
        except ValueError:
            continue
    return tags


def etag_matches(
    etag: str, candidates: Iterable[str], weak_compare: bool = True
) -> bool:
    try:
        normalized = normalize_etag(etag)
    except ValueError:
        return False

    def strip_weak(value: str) -> str:
        return value[2:] if value.startswith(_WEAK_PREFIX) else value

    for candidate in candidates:
        try:
            normalized_candidate = normalize_etag(candidate)
        except ValueError:
            continue
        if weak_compare:
            if strip_weak(normalized_candidate) == strip_weak(normalized):
                return True
        elif normalized_candidate == normalized:
            return True
    return False


def is_fresh(ctx: HttpContext, response: BaseResponse, weak_compare: bool = True) -> bool:
    current = response.headers.get("etag")
    if not current:
        return False
    return etag_matches(
        current, parse_if_none_match(ctx), weak_compare=weak_compare
    )


class ETagMiddleware(BaseMiddleware):
    """Compute ETag headers and handle ``If-None-Match`` conditionals."""

    def __init__(
        self,
        *,
        weak: bool = True,
        methods: Iterable[str] = ("GET", "HEAD"),
        override: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.weak = weak
        self.methods = tuple(method.upper() for method in methods)
        self.override = override

    async def dispatch(self, ctx: HttpContext, call_next: Any) -> Any:
        """Run the chain, then attach an ETag and honour ``If-None-Match``."""
        response = await call_next()

        if response is None or ctx.method.upper() not in self.methods:
            return response

        has_existing = bool(response.headers.get("etag"))
        if not has_existing or self.override:
            body = _response_body(response)
            if body is not None:
                compute_and_set_etag(response, body, weak=self.weak, override=True)

        if is_fresh(ctx, response, weak_compare=True):
            return _not_modified(response)

        return response


#: Headers RFC 9110 §15.4.5 requires a 304 to carry when the corresponding
#: 200 would have carried them. Everything else is dropped: a 304 says "your
#: copy is current", so describing a body that is not being sent is noise at
#: best and contradictory at worst.
_NOT_MODIFIED_HEADERS = (
    "etag",
    "cache-control",
    "content-location",
    "date",
    "expires",
    "vary",
)


def _not_modified(response: BaseResponse) -> BaseResponse:
    """Build the 304 to send in place of *response*.

    A fresh response cannot be turned into a 304 by mutating it. What arrives
    here is a streaming response replaying the inner application's body from a
    memory stream, and ``set_body`` writes an attribute that the streaming
    path never reads — so the status changed to 304, ``Content-Length`` was
    set to 0, and the original body went out behind it. A 304 carrying a body
    is a protocol violation, and one whose declared length disagrees with what
    it sends can desync a keep-alive connection.

    Returning a new response replaces the streaming one outright, which is the
    only way to guarantee nothing follows the headers.
    """
    headers = {
        name: value
        for name, value in response.headers.items()
        if name.lower() in _NOT_MODIFIED_HEADERS
    }

    return BaseResponse(body=b"", status_code=304, headers=headers)


def _response_body(response: BaseResponse) -> bytes | None:
    try:
        body = response.body
    except AttributeError:
        return None
    if isinstance(body, bytes):
        return body
    if isinstance(body, memoryview):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    return None


def ETag(
    weak: bool = True, methods: Iterable[str] = ("GET", "HEAD"), override: bool = False
) -> ETagMiddleware:
    return ETagMiddleware(weak=weak, methods=methods, override=override)


__all__ = [
    "ETag",
    "ETagMiddleware",
    "compute_and_set_etag",
    "etag_matches",
    "generate_etag_from_bytes",
    "is_fresh",
    "normalize_etag",
    "parse_if_match",
    "parse_if_none_match",
    "set_response_etag",
]
