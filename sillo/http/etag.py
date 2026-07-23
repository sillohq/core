from __future__ import annotations

import re
from base64 import b64encode
from hashlib import sha1
from typing import Any, Iterable

from sillo.core.http import Request, Response
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


def set_response_etag(response: Response, etag: str, override: bool = True) -> None:
    response.set_header("etag", normalize_etag(etag), overide=override)


def compute_and_set_etag(
    response: Response, body: bytes = b"", weak: bool = True, override: bool = False
) -> str:
    tag = generate_etag_from_bytes(body, weak=weak)
    set_response_etag(response, tag, override=override)
    return tag


def parse_if_none_match(request: Request) -> list[str]:
    return _parse_etag_list(request.headers.get("if-none-match"))


def parse_if_match(request: Request) -> list[str]:
    return _parse_etag_list(request.headers.get("if-match"))


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


def is_fresh(request: Request, response: Response, weak_compare: bool = True) -> bool:
    current = response.headers.get("etag")
    if not current:
        return False
    return etag_matches(current, parse_if_none_match(request), weak_compare=weak_compare)


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

    async def process_request(
        self, request: Request, response: Response, call_next: Any
    ) -> Any:
        return await call_next()

    async def process_response(self, request: Request, response: Response) -> Any:
        if request.method.upper() not in self.methods:
            return response
        if not getattr(response, "_response", None):
            return response

        has_existing = bool(response.headers.get("etag"))
        if not has_existing or self.override:
            body = _response_body(response)
            if body is not None:
                compute_and_set_etag(response, body, weak=self.weak, override=True)

        if is_fresh(request, response, weak_compare=True):
            response.status(304)
            response.set_body(b"")
            response.set_header("content-length", "0", overide=True)

        return response


def _response_body(response: Response) -> bytes | None:
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
    "ETagMiddleware",
    "ETag",
    "generate_etag_from_bytes",
    "normalize_etag",
    "set_response_etag",
    "compute_and_set_etag",
    "parse_if_none_match",
    "parse_if_match",
    "etag_matches",
    "is_fresh",
]
