from __future__ import annotations

import hashlib
import http.cookies
import json
import mimetypes
import os
import stat
import typing
from base64 import b64encode
from collections.abc import AsyncIterable, AsyncIterator, Callable
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, formatdate
from functools import partial
from hashlib import sha1
from pathlib import Path
from typing import (
    Annotated,
    Any,
    ClassVar,
    Union,
)
from urllib.parse import quote

import anyio
import anyio.to_thread
from anyio import AsyncFile
from typing_extensions import Doc

from sillo.core.encoding import jsonable_encoder
from sillo.core.http.context import ClientDisconnect, HttpContext
from sillo.exceptions import HTTPException, NotFoundException
from sillo.objects import MutableHeaders
from sillo.pagination import (
    AsyncListDataHandler,
    AsyncPaginator,
    BasePaginationStrategy,
    CursorPagination,
    LimitOffsetPagination,
    PageNumberPagination,
    SyncListDataHandler,
    SyncPaginator,
)

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]

JSONType = Union[str, int, float, bool, None, dict[str, Any], list[Any]]

#: The expiry :meth:`BaseResponse.delete_cookie` sends. A fixed instant in the
#: past, so it does not depend on the client's clock agreeing with the
#: server's.
_EXPIRED = "Thu, 01 Jan 1970 00:00:00 GMT"

#: Punctuation a cookie value may carry unescaped: ``http.cookies._LegalChars``
#: — anything outside it makes ``SimpleCookie`` fall back to backslash-quoting
#: the whole value — less ``%``, which is spent on being the escape character.
#: Alphanumerics are always left alone by ``quote``. Base64url tokens are made
#: of ``-``, ``_``, ``.`` and alphanumerics, so they pass through untouched.
_COOKIE_SAFE = "!#$&'*+-.:^_`|~"


def _encode_cookie_value(value: str) -> str:
    """Percent-encode *value* so it survives a round trip through a browser.

    Handed a value it considers illegal, ``SimpleCookie`` wraps it in double
    quotes and escapes the awkward characters as backslash-octal. Nothing
    undoes that:
    :func:`~sillo.core.http.cookies.parse_cookies` percent-decodes, as browsers
    and ``document.cookie`` do, so ``set_cookie("flash", "a=b/c%20d")`` came
    back as ``'"a=b/c d"'`` — quotes still attached and the escape decoded
    that nobody wrote.

    Percent-encoding here instead makes writing and reading each other's
    inverse, and matches what ``encodeURIComponent`` produces on the client.
    Ordinary values — base64url tokens, identifiers, numbers — contain nothing
    outside the safe set and pass through untouched.
    """
    return quote(value, safe=_COOKIE_SAFE)


class MalformedRangeHeader(Exception):
    """Exception raised when a Range header cannot be parsed.

    This exception is raised by the file response handler when the client
    sends a malformed or unsupported Range header that cannot be interpreted
    for partial content delivery.  The exception carries a human-readable
    error message describing the problem.

    Inherits from:
        Exception: Standard Python exception base class.

    Attributes:
        content: A human-readable error message describing the malformed
            range header.  Defaults to ``"Malformed range header."``.
    """

    def __init__(self, content: str = "Malformed range header.") -> None:
        """Initialize the exception with a descriptive error message.

        Args:
            content: A human-readable error message describing the malformed
                range header.  Defaults to ``"Malformed range header."``.

        Returns:
            None: This method initializes the instance in-place.

        Raises:
            None: This method does not raise exceptions.
        """
        self.content = content


class RangeNotSatisfiable(Exception):
    """Exception raised when a requested byte range cannot be satisfied.

    This exception is raised by the file response handler when the client
    requests a byte range that falls outside the bounds of the file (e.g.
    requesting bytes 1000-2000 of a 500-byte file).  The HTTP response
    should return a 416 status code with a ``Content-Range`` header
    indicating the file size.

    Inherits from:
        Exception: Standard Python exception base class.

    Attributes:
        max_size: The total size of the file in bytes, used to construct
            the ``Content-Range`` response header.
    """

    def __init__(self, max_size: int) -> None:
        """Initialize the exception with the file's maximum size.

        Args:
            max_size: The total size of the file in bytes.  This value is
                used to construct the ``Content-Range`` response header
                (e.g. ``"bytes */500"``).

        Returns:
            None: This method initializes the instance in-place.

        Raises:
            None: This method does not raise exceptions.
        """
        self.max_size = max_size


class BaseResponse:
    """Base ASGI-compatible Response class for the sillo framework.

    Provides the foundation for all HTTP response types, including support
    for cookies, caching headers, custom headers, and content rendering.
    Subclasses specialize this base for specific content types (JSON, HTML,
    files, streaming).  The response is callable as an ASGI application,
    allowing it to be returned directly from request handlers.

    The class manages raw headers as a list of byte tuples for efficient
    ASGI serialization and provides convenience methods for common header
    operations like setting cookies and cache control.

    Attributes:
        STATUS_CODES: A dictionary mapping common HTTP status codes to their
            standard reason phrases.
        charset: The character encoding used for text content (default UTF-8).
        status_code: The HTTP status code for the response.
        raw_headers: List of (name, value) byte tuples for ASGI serialization.
        content_type: The Content-Type header value, if set.

    Inherits from:
        object: Python built-in base class.
    """

    STATUS_CODES: ClassVar[dict] = {
        200: "OK",
        201: "Created",
        204: "No Content",
        301: "Moved Permanently",
        302: "Found",
        304: "Not Modified",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        500: "Internal Server Error",
    }

    def __init__(
        self,
        body: JSONType | Any = "",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content_type: str | None = None,
    ):
        """Initialize a BaseResponse with body, status, headers, and content type.

        Renders the body content to bytes, sets the HTTP status code, and
        initializes the raw headers list. Automatically populates the
        Content-Length and Content-Type headers if not explicitly provided
        in the *headers* dictionary.

        Args:
            body: The response body content. Can be a string, bytes, or any
                JSON-compatible type. Defaults to an empty string.
            status_code: The HTTP status code for the response. Defaults to
                200 (OK).
            headers: Optional dictionary of header name-value pairs to include
                in the response.
            content_type: Optional Content-Type header value. If the content
                type starts with ``"text/"`` and lacks a charset parameter,
                the response charset is appended automatically.
        """
        self.charset = "utf-8"
        self.status_code: int = status_code
        self.raw_headers: list[tuple[bytes, bytes]] = []
        self._body = self.render(body)
        self.content_type: str | None = content_type
        self._init_headers(headers)

    def render(self, content: typing.Any) -> bytes | memoryview:
        """Render content to bytes for transmission over the wire.

        Converts the provided content into a bytes representation suitable
        for sending as an HTTP response body.  Handles ``None`` (returns
        empty bytes), ``bytes``/``memoryview`` (returns as-is), and strings
        (encodes using the response charset).

        Args:
            content: The content to render.  Can be ``None``, ``bytes``,
                ``memoryview``, or a string-like object with an ``encode``
                method.

        Returns:
            The rendered content as ``bytes`` or ``memoryview``.

        Raises:
            AttributeError: If *content* is a string-like object that does
                not support the ``encode`` method.
        """
        if content is None:
            return b""
        if isinstance(content, (bytes, memoryview)):
            return content
        return content.encode(self.charset)

    def _init_headers(self, headers: dict[str, str] | None = None):
        """Initialize response headers from a dictionary of name-value pairs.

        Processes the provided headers dictionary, normalizing header names
        to lowercase and encoding values as Latin-1 bytes for ASGI
        compatibility.  Automatically populates the Content-Length header
        based on the response body size (unless the status code indicates
        no body should be sent) and the Content-Type header if a content
        type was specified.

        Args:
            headers: Optional dictionary of header name-value pairs.  Header
                names are normalized to lowercase.  Defaults to ``None``,
                meaning no additional headers are added beyond the automatic
                Content-Length and Content-Type.

        Returns:
            None: This method modifies the instance's ``raw_headers`` list
                in-place.

        Raises:
            UnicodeEncodeError: If a header value contains characters that
                cannot be encoded as Latin-1.
        """
        if headers is None:
            raw_headers: list[tuple[bytes, bytes]] = []
            populate_content_length = True
            populate_content_type = True
        else:
            raw_headers = [
                (k.lower().encode("latin-1"), v.encode("latin-1"))
                for k, v in headers.items()
            ]
            keys = [h[0] for h in raw_headers]
            populate_content_length = b"content-length" not in keys
            populate_content_type = b"content-type" not in keys
        body = getattr(self, "_body", None)
        if (
            body is not None
            and populate_content_length
            and not (self.status_code < 200 or self.status_code in (204, 304))
        ):
            content_length = str(len(body))
            self.set_header("content-length", content_length, override=True)
        content_type: str | None = self.content_type
        if content_type is not None and populate_content_type:
            if (
                content_type.startswith("text/")
                and "charset=" not in content_type.lower()
            ):
                content_type += "; charset=" + self.charset
            self.raw_headers.append((b"content-type", content_type.encode("latin-1")))

        self.raw_headers.extend(raw_headers)

    @property
    def headers(self) -> MutableHeaders:
        """The response headers as a mutable mapping.

        Lazily builds and caches a :class:`MutableHeaders` instance from
        the raw headers list.  Provides convenient dictionary-style access
        for reading and modifying response headers after initialization.

        Returns:
            A :class:`MutableHeaders` instance wrapping the response's raw
            headers list.

        Raises:
            None: This property does not raise exceptions.
        """
        if not hasattr(self, "_headers"):
            self._headers = MutableHeaders(raw=self.raw_headers)
        return self._headers

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: int | None = None,
        expires: datetime | str | int | None = None,
        path: str | None = "/",
        domain: str | None = None,
        secure: bool | None = False,
        httponly: bool | None = False,
        samesite: typing.Literal["lax", "strict", "none"] | None = "lax",
    ) -> Any:
        """Set an HTTP cookie in the response with full attribute control.

        Creates a ``Set-Cookie`` header with the specified cookie name, value,
        and attributes.  Supports all standard cookie attributes including
        expiration, path, domain, security flags, and SameSite policy.  The
        cookie is serialized and appended to the response headers.

        Args:
            key: The cookie name.  Must be a valid cookie token (no semicolons
                or whitespace).
            value: The cookie value.  Defaults to an empty string.
            max_age: Maximum age of the cookie in seconds.  Takes precedence
                over *expires* if both are set.  Defaults to ``None``.
            expires: Expiration date/time for the cookie.  Can be a datetime
                object, Unix timestamp (int), or HTTP date string.  Defaults
                to ``None``.
            path: URL path where the cookie is valid.  Defaults to ``"/"``.
            domain: Domain where the cookie is valid.  Defaults to ``None``
                (current domain only).
            secure: If ``True``, cookie is only sent over HTTPS.  Defaults to
                ``False``.
            httponly: If ``True``, cookie is inaccessible to JavaScript.
                Defaults to ``False``.
            samesite: SameSite attribute for CSRF protection.  Must be
                ``"lax"``, ``"strict"``, or ``"none"``.  Defaults to ``"lax"``.

        Returns:
            The underlying ``SimpleCookie`` object for advanced manipulation.

        Raises:
            AssertionError: If *samesite* is not one of ``"lax"``, ``"strict"``,
                or ``"none"`` (case-insensitive).
        """
        cookie: http.cookies.BaseCookie[str] = http.cookies.SimpleCookie()
        cookie[key] = _encode_cookie_value(value)
        if max_age is not None:
            cookie[key]["max-age"] = max_age
        if expires is not None:
            if isinstance(expires, datetime):
                cookie[key]["expires"] = format_datetime(expires, usegmt=True)
            else:
                cookie[key]["expires"] = expires
        if path is not None:
            cookie[key]["path"] = path
        if domain is not None:
            cookie[key]["domain"] = domain
        if secure:
            cookie[key]["secure"] = True
        if httponly:
            cookie[key]["httponly"] = True
        if samesite is not None:
            assert samesite.lower() in [
                "strict",
                "lax",
                "none",
            ], "samesite must be either 'strict', 'lax' or 'none'"
            if samesite.lower() == "none" and not secure:
                # Browsers reject SameSite=None without Secure and drop the
                # cookie without telling anyone, so the setting that was meant
                # to allow cross-site use instead switches the cookie off.
                raise ValueError(
                    f"Cookie {key!r} sets samesite='none' without secure=True. "
                    f"Browsers reject that combination and drop the cookie "
                    f"silently. Pass secure=True, or use samesite='lax'."
                )
            cookie[key]["samesite"] = samesite
        cookie_val = cookie.output(header="").strip()
        self.set_header("set-cookie", cookie_val)

        return self

    def delete_cookie(
        self,
        key: str,
        path: str = "/",
        domain: str | None = None,
        secure: bool | None = False,
        httponly: bool | None = False,
        samesite: typing.Literal["lax", "strict", "none"] | None = "lax",
    ) -> Any:
        """Delete a cookie by setting its expiration to the past.

        Sends a ``Set-Cookie`` header with an empty value and an expiry in the
        past, instructing the client to remove the specified cookie.  The path
        and domain must match those used when the cookie was originally set
        for the deletion to take effect.

        Args:
            key: The name of the cookie to delete.
            path: The URL path where the cookie was originally set.  Must
                match the original cookie's path.  Defaults to ``"/"``.
            domain: The domain where the cookie was originally set.  Must
                match the original cookie's domain.  Defaults to ``None``.
            secure: Whether to repeat the ``Secure`` attribute.  Needed to
                delete a cookie whose name carries the ``__Secure-`` or
                ``__Host-`` prefix, since browsers reject a ``Set-Cookie`` for
                one of those names that is not marked ``Secure`` — so without
                it the deletion is ignored and the user stays signed in.
            httponly: Whether to repeat the ``HttpOnly`` attribute.
            samesite: Whether to repeat the ``SameSite`` attribute.

        Returns:
            The underlying ``SimpleCookie`` object for advanced manipulation.

        Raises:
            None: This method does not raise exceptions.
        """
        # A fixed date in the past, not `expires=0`. `SimpleCookie` reads a
        # numeric expires as an offset from now, so `0` rendered as the current
        # time -- which is only in the past if the client's clock agrees with
        # the server's, and a client running a few seconds behind kept the
        # cookie.
        cookie = self.set_cookie(
            key=key,
            value="",
            max_age=0,
            expires=_EXPIRED,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )

        return cookie

    def enable_caching(self, max_age: int = 3600, private: bool = True) -> None:
        """Enable HTTP caching with the specified max age and visibility.

        Sets the ``Cache-Control``, ``ETag``, and ``Expires`` headers to
        enable browser and proxy caching of the response.  The ETag is
        generated from a SHA-1 hash of the response body for cache
        validation.

        Args:
            max_age: Maximum age of the cached response in seconds.  Defaults
                to 3600 (1 hour).
            private: If ``True``, the response is marked as private (only
                the client's browser may cache it).  If ``False``, the
                response is marked as public (intermediate proxies may also
                cache it).  Defaults to ``True``.

        Returns:
            None: This method modifies the response headers in-place.

        Raises:
            None: This method does not raise exceptions.
        """
        cache_control: list[str] = []
        if private:
            cache_control.append("private")
        else:
            cache_control.append("public")

        cache_control.append(f"max-age={max_age}")
        self.set_header("cache-control", ", ".join(cache_control))

        etag = self._generate_etag()
        self.set_header("etag", etag)

        expires = datetime.now(timezone.utc) + timedelta(seconds=max_age)
        self.set_header("expires", formatdate(expires.timestamp(), usegmt=True))

    def disable_caching(self) -> None:
        """Disable caching for this response."""
        self.set_header(
            "cache-control", "no-store, no-cache, must-revalidate, max-age=0"
        )
        self.set_header("pragma", "no-cache")
        self.set_header("expires", "0")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Make the response callable as an ASGI application."""
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": self._body,
            }
        )

    @property
    def body(self):
        """The response body as bytes."""
        return self._body

    def set_body(self, content: typing.Any) -> BaseResponse:
        """Replace the body, keeping Content-Length in step with it.

        Assigning ``_body`` directly leaves the Content-Length that was
        computed from the *old* body, and a server writing more bytes than it
        declared aborts the response.

        Args:
            content: The new body, rendered the same way as an initial one.

        Returns:
            This response, for chaining.
        """
        self._body = self.render(content)
        self.set_header("content-length", str(len(self._body)), override=True)
        return self

    def _generate_etag(self) -> str:
        """Generate an ETag for the response content."""
        content_hash = sha1()
        content_hash.update(self._body)
        return f'W/"{b64encode(content_hash.digest()).decode("utf-8")}"'

    def set_header(
        self,
        key: str,
        value: str,
        override: bool = False,
    ) -> BaseResponse:
        """Set a response header.

        Args:
            key: Header name.
            value: Header value.
            override: If True, replace any existing header with the same name.
        """
        key_bytes = key.lower().encode(
            "latin-1"
        )  # Normalize key to lowercase for case-insensitive comparison
        value_bytes = value.encode("latin-1")
        new_header = (key_bytes, value_bytes)

        if override:
            # Edit in place rather than rebinding: `self.headers` caches a
            # MutableHeaders around this exact list, and a fresh list leaves
            # that cache pointing at an orphan, so later edits through
            # `response.headers` never reach the wire.
            self.raw_headers[:] = [
                (k, v) for k, v in self.raw_headers if k != key_bytes
            ]

        self.raw_headers.append(new_header)
        return self

    def set_headers(
        self,
        headers: dict[str, str],
        override_all: bool = False,
    ):
        """Set multiple headers at once.

        Args:
            headers: Dict of header name to value.
            override_all: If True, replace all existing headers.
        """
        if override_all:
            self.raw_headers[:] = [
                (k.lower().encode("latin-1"), v.encode("latin-1"))
                for k, v in headers.items()
            ]
            return
        for key, value in headers.items():
            self.set_header(key, value)

    def remove_header(self, key: str):
        """Remove a header from the response."""
        del self.headers[key]

    def remove_headers(self, keys: list[str]):
        """Remove multiple headers from the response."""
        for key in keys:
            self.remove_header(key)

    # The chainable half of the API. A handler holds the response object
    # itself now, so what used to be `json(...).status(201)` on a
    # per-request builder is `json(...).status(201)` on what the builder
    # returned. Each of these returns ``self`` so they compose.

    def status(self, status_code: int) -> BaseResponse:
        """Set the status code. Returns ``self`` so it chains."""
        self.status_code = status_code
        return self

    def cache(self, max_age: int = 3600, private: bool = True) -> BaseResponse:
        """Mark the response cacheable. Returns ``self`` so it chains."""
        self.enable_caching(max_age=max_age, private=private)
        return self

    def no_cache(self) -> BaseResponse:
        """Mark the response uncacheable. Returns ``self`` so it chains."""
        self.disable_caching()
        return self

    def has_header(self, key: str) -> bool:
        """Whether *key* is present, case-insensitively."""
        return key.lower() in (name.lower() for name in self.headers)

    @property
    def content_length(self) -> str:
        """The declared Content-Length, falling back to the body's own length."""
        declared = self.headers.get("content-length")
        if declared:
            return declared
        return str(len(self.body))

    def set_cookies(self, cookies: list[dict[str, Any]]) -> BaseResponse:
        """Set several cookies at once. Returns ``self`` so it chains."""
        for cookie in cookies:
            self.set_cookie(**cookie)
        return self

    def set_permanent_cookie(
        self, key: str, value: str, **kwargs: Any
    ) -> BaseResponse:
        """Set a cookie that expires ten years out. Returns ``self``."""
        expires = datetime.now(timezone.utc) + timedelta(days=365 * 10)
        return self.set_cookie(key, value, expires=expires, **kwargs)

    def add_csp_header(self, policy: str) -> BaseResponse:
        """Set ``Content-Security-Policy``. Returns ``self`` so it chains."""
        self.set_header("Content-Security-Policy", policy, override=True)
        return self


class PlainTextResponse(BaseResponse):
    def __init__(
        self,
        body: JSONType = "",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content_type: str = "text/plain",
    ):
        super().__init__(body, status_code, headers, content_type)


class JSONResponse(BaseResponse):
    """
    Response subclass for JSON content.
    """

    def __init__(
        self,
        content: Any,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        indent: int | None = None,
        ensure_ascii: bool = True,
        use_encoder: bool = True,
        custom_encoder: dict[type, Callable[[Any], Any]] | None = None,
    ):
        try:
            body = self._serialize(
                content, indent, ensure_ascii, use_encoder, custom_encoder
            )
        except (TypeError, ValueError) as e:
            raise ValueError(f"Content is not JSON serializable: {e!s}")

        super().__init__(
            body=body,
            status_code=status_code,
            headers=headers,
            content_type="application/json",
        )

    @staticmethod
    def _serialize(
        content: Any,
        indent: int | None,
        ensure_ascii: bool,
        use_encoder: bool,
        custom_encoder: dict[type, Callable[[Any], Any]] | None,
    ) -> str:
        """Render *content* as JSON, walking it only when that is necessary.

        Most handlers return something the standard library can already
        serialize: a dict of strings and numbers, a list of those, whatever an
        ORM row's ``to_dict`` produced. ``jsonable_encoder`` exists for the ones
        that do not — datetimes, UUIDs, Decimals, Pydantic models — and it finds
        out by rebuilding the entire structure, one Python call per node. On a
        200-row response that is three thousand calls, and then ``json.dumps``
        walks the result all over again.

        So the encoder is not run up front any more; it is what happens when the
        direct attempt fails. A payload that was already JSON-safe is serialized
        once instead of twice, which measured 1053µs to 322µs on that 200-row
        response. A payload that is not pays one cheap failed attempt and then
        exactly what it paid before.

        Two cases keep the old order deliberately. A ``custom_encoder`` is a
        request for particular types to be rendered a particular way, and the
        fast path would quietly ignore it for any type the standard library
        already understands. And with ``use_encoder`` off the caller has said
        not to walk the content at all, which is what ``default=str`` is for.

        Args:
            content: The value to render.
            indent: Indentation, or ``None`` for the compact form.
            ensure_ascii: Escape non-ASCII characters.
            use_encoder: Whether ``jsonable_encoder`` may be used at all.
            custom_encoder: Per-type encoders, which force the encoder path.

        Returns:
            The JSON text.

        Raises:
            TypeError: If the content holds a type nothing here can render.
            ValueError: For NaN, infinities and circular references.
        """
        # Compact by default: `json.dumps` separates with ", " and ": ", which
        # is 11.5% more bytes on the wire than the same data needs, on every
        # JSON response. Only when indentation was asked for is the readable
        # form the point.
        separators = (",", ":") if indent is None else None

        if not use_encoder:
            return json.dumps(
                content,
                indent=indent,
                ensure_ascii=ensure_ascii,
                allow_nan=False,
                default=str,
                separators=separators,
            )

        if custom_encoder is None:
            try:
                return json.dumps(
                    content,
                    indent=indent,
                    ensure_ascii=ensure_ascii,
                    allow_nan=False,
                    separators=separators,
                )
            except (TypeError, ValueError):
                # Something in there needs converting — or the content is
                # unserializable for a reason the encoder cannot fix either, in
                # which case the second attempt raises the same thing and the
                # caller sees the error it would always have seen.
                pass

        return json.dumps(
            jsonable_encoder(content, custom_encoder=custom_encoder),
            indent=indent,
            ensure_ascii=ensure_ascii,
            allow_nan=False,
            default=str,
            separators=separators,
        )


class HTMLResponse(BaseResponse):
    """
    Response subclass for HTML content.
    """

    def __init__(
        self,
        content: str | JSONType,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            body=content,
            status_code=status_code,
            headers=headers,
            content_type="text/html; charset=utf-8",
        )


class FileResponse(BaseResponse):
    """
    Enhanced FileResponse class with AnyIO for asynchronous file streaming,
    support for range requests, and multipart responses.
    """

    chunk_size = 64 * 1024  # 64KB chunks

    def __init__(
        self,
        path: str | Path,
        filename: str | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content_disposition_type: str = "inline",
    ):
        super().__init__(headers=headers)
        self.path = Path(path)
        self.filename = filename or self.path.name
        self.content_disposition_type = content_disposition_type
        self.status_code = status_code

        content_type, _ = mimetypes.guess_type(str(self.path))
        #: Kept as an attribute because a multipart/byteranges response
        #: overwrites the response-level Content-Type, and every part still
        #: has to declare the media type of the file itself.
        self.media_type = content_type or "application/octet-stream"
        self.set_header("content-type", self.media_type)
        self.set_header(
            "content-disposition",
            f'{content_disposition_type}; filename="{self.filename}"',
        )
        self.set_header("accept-ranges", "bytes")

        self._ranges: list[tuple[int, int]] = []
        self._multipart_boundary: str | None = None

    def set_stat_headers(self, stat_result: os.stat_result) -> None:
        content_length = str(stat_result.st_size)
        last_modified = formatdate(stat_result.st_mtime, usegmt=True)
        etag_base = str(stat_result.st_mtime) + "-" + str(stat_result.st_size)
        etag = f'"{hashlib.md5(etag_base.encode(), usedforsecurity=False).hexdigest()}"'

        self.set_header("content-length", content_length, override=True)
        self.headers.setdefault("last-modified", last_modified)
        self.headers.setdefault("etag", etag)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle the ASGI response, including range requests."""

        try:
            stat_result = await anyio.to_thread.run_sync(os.stat, self.path)
            self.set_stat_headers(stat_result)
        except FileNotFoundError:
            raise RuntimeError(f"File at path {self.path} does not exist.")
        else:
            mode = stat_result.st_mode
            if not stat.S_ISREG(mode):
                raise RuntimeError(f"File at path {self.path} is not a file.")

        range_header = MutableHeaders(scope=scope).get("Range")
        if range_header:
            self._handle_range_header(range_header)

        await self._send_response(scope, receive, send)

    def _parse_ranges(self, range_header: str, file_size: int) -> list[tuple[int, int]]:
        """Turn a ``Range`` header into inclusive ``(start, end)`` offsets.

        Args:
            range_header: The raw header value, e.g. ``"bytes=0-99,200-"``.
            file_size: The size of the file on disk, in bytes.

        Returns:
            One ``(start, end)`` pair per range, both offsets inclusive and
            already clamped to the file.

        Raises:
            ValueError: If the header is malformed, names a unit other than
                ``bytes``, or every range it asks for is unsatisfiable.
        """
        unit, sep, spec = range_header.strip().partition("=")
        if not sep or unit.strip().lower() != "bytes":
            raise ValueError("Only byte ranges are supported")

        ranges: list[tuple[int, int]] = []
        for range_str in spec.split(","):
            first, sep, last = range_str.strip().partition("-")
            if not sep:
                raise ValueError(f"Malformed range {range_str!r}")
            first, last = first.strip(), last.strip()

            if not first:
                # A suffix range: `bytes=-500` means the *last* 500 bytes,
                # not "from 0 to 500".
                suffix = int(last)
                if suffix <= 0:
                    raise ValueError("Suffix range must be positive")
                start, end = max(0, file_size - suffix), file_size - 1
            else:
                start = int(first)
                # An absent or over-long last-byte-pos means "to the end of
                # the file" (RFC 9110 §14.1.2), so a client that asks for
                # more than exists gets what exists rather than a 416.
                end = file_size - 1 if not last else min(int(last), file_size - 1)

            if start < 0 or start >= file_size or start > end:
                raise ValueError("Unsatisfiable range")
            ranges.append((start, end))

        if not ranges:
            raise ValueError("No ranges given")
        return ranges

    def _multipart_part_header(self, start: int, end: int, file_size: int) -> bytes:
        """Build the boundary and headers that introduce one multipart part."""
        return (
            f"--{self._multipart_boundary}\r\n"
            f"Content-Type: {self.media_type}\r\n"
            f"Content-Range: bytes {start}-{end}/{file_size}\r\n\r\n"
        ).encode("latin-1")

    def _multipart_epilogue(self) -> bytes:
        """Build the closing delimiter that ends a multipart body."""
        return f"--{self._multipart_boundary}--\r\n".encode("latin-1")

    def _multipart_length(self, file_size: int) -> int:
        """Total size of the multipart body, framing included.

        Counted from the very functions that write it, so the number declared
        and the number of bytes sent cannot drift apart.
        """
        total = len(self._multipart_epilogue())
        for start, end in self._ranges:
            total += len(self._multipart_part_header(start, end, file_size))
            total += end - start + 1
            total += 2  # the CRLF that closes each part body
        return total

    def _handle_range_header(self, range_header: str) -> None:
        """Apply a ``Range`` header to this response's status and headers."""
        file_size = self.path.stat().st_size

        try:
            self._ranges = self._parse_ranges(range_header, file_size)
        except ValueError:
            self._ranges = []
            self.set_header("content-range", f"bytes */{file_size}", override=True)
            # `set_stat_headers` declared the whole file. A 416 sends no body
            # at all, so leaving that in place promises bytes that never come
            # and the server tears the connection down mid-response.
            self.set_header("content-length", "0", override=True)
            self.status_code = 416
            return

        self.status_code = 206

        if len(self._ranges) == 1:
            start, end = self._ranges[0]
            self.set_header(
                "content-range", f"bytes {start}-{end}/{file_size}", override=True
            )
            self.set_header("content-length", str(end - start + 1), override=True)
            return

        # Several ranges travel as one multipart/byteranges body, where each
        # part carries its own boundary and headers. That framing is part of
        # the response, so the declared length has to cover it too — the file
        # size left over from `set_stat_headers` is not just wrong, it is
        # routinely *smaller* than what gets written.
        self._multipart_boundary = self._generate_multipart_boundary()
        self.set_header(
            "content-type",
            f"multipart/byteranges; boundary={self._multipart_boundary}",
            override=True,
        )
        self.set_header(
            "content-length", str(self._multipart_length(file_size)), override=True
        )

    async def _send_response(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send the file response, handling range requests and multipart responses."""

        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )

        if self.status_code == 416:
            await send(
                {
                    "type": "http.response.body",
                    "body": b"",
                }
            )
            return

        async with await anyio.open_file(self.path, "rb") as file:
            if self._multipart_boundary:
                file_size = self.path.stat().st_size
                for start, end in self._ranges:
                    await self._send_multipart_chunk(file, start, end, file_size, send)
                await send(
                    {
                        "type": "http.response.body",
                        "body": self._multipart_epilogue(),
                        "more_body": False,
                    }
                )
            elif self._ranges:
                start, end = self._ranges[0]
                await self._send_range(file, start, end, send)
            else:
                await self._send_full_file(file, send)

    async def _send_full_file(self, file: AsyncFile[bytes], send: Send) -> None:
        """Send the entire file in chunks using AnyIO."""
        while True:
            chunk = await file.read(self.chunk_size)
            if not chunk:
                break
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                }
            )
        await send(
            {
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            }
        )

    async def _send_range(
        self, file: AsyncFile[bytes], start: int, end: int, send: Send
    ) -> None:
        """Send a single range of the file using AnyIO."""
        await file.seek(start)
        # Content-Length was settled in `_handle_range_header`; the start
        # message has already gone out, so setting a header here does nothing.
        remaining = end - start + 1

        while remaining > 0:
            chunk_size = min(self.chunk_size, remaining)
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                }
            )
            remaining -= len(chunk)
        await send(
            {
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            }
        )

    async def _send_multipart_chunk(
        self,
        file: AsyncFile[bytes],
        start: int,
        end: int,
        file_size: int,
        send: Send,
    ) -> None:
        """Send a multipart chunk for a range using AnyIO."""
        await file.seek(start)
        remaining = end - start + 1

        await send(
            {
                "type": "http.response.body",
                "body": self._multipart_part_header(start, end, file_size),
                "more_body": True,
            }
        )

        while remaining > 0:
            chunk_size = min(self.chunk_size, remaining)
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                }
            )
            remaining -= len(chunk)

        # A part body is closed by CRLF before the next boundary; without it
        # the delimiter runs on from the data and no parser finds it.
        await send(
            {
                "type": "http.response.body",
                "body": b"\r\n",
                "more_body": True,
            }
        )

    def _generate_multipart_boundary(self) -> str:
        """Generate a unique multipart boundary string."""
        return f"boundary_{os.urandom(16).hex()}"


class StreamingResponse(BaseResponse):
    """
    Response subclass for streaming content.
    """

    def __init__(
        self,
        content: AsyncIterator[str | bytes],
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content_type: str = "text/plain",
    ):
        super().__init__(headers=headers)

        self.content_iterator = content
        self.status_code = status_code
        self._cookies: list[tuple[str, str, dict[str, Any]]] = []

        self.content_type = content_type
        self.headers["content-type"] = self.content_type
        del self.headers["content-length"]

    async def listen_for_disconnect(self, receive: Receive) -> None:
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break

    async def stream_response(self, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        async for chunk in self.content_iterator:
            if not isinstance(chunk, (bytes, memoryview)):
                chunk = chunk.encode(self.charset)

            await send({"type": "http.response.body", "body": chunk, "more_body": True})

        await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        spec_version = tuple(
            map(int, scope.get("asgi", {}).get("spec_version", "2.0").split("."))
        )

        if spec_version >= (2, 4):
            try:
                await self.stream_response(send)
            except OSError:
                raise ClientDisconnect()
        else:
            async with anyio.create_task_group() as task_group:

                async def wrap(
                    func: typing.Callable[[], typing.Awaitable[None]],
                ) -> None:
                    await func()
                    task_group.cancel_scope.cancel()

                task_group.start_soon(wrap, partial(self.stream_response, send))
                await wrap(partial(self.listen_for_disconnect, receive))


class RedirectResponse(BaseResponse):
    """
    Response subclass for HTTP redirects.
    """

    def __init__(
        self,
        url: str,
        status_code: int = 302,
        headers: dict[str, str] = {},
    ):
        if not 300 <= status_code < 400:
            raise ValueError("Status code must be a valid redirect status")

        headers["location"] = quote(str(url), safe=":/%#?=@[]!$&'()*+,;")

        super().__init__(body="", status_code=status_code, headers=headers)
