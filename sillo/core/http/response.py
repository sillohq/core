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

from sillo.core.http.request import ClientDisconnect, Request
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
            self.set_header("content-length", content_length, overide=True)
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
        cookie[key] = value
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
            cookie[key]["samesite"] = samesite
        cookie_val = cookie.output(header="").strip()
        self.set_header("set-cookie", cookie_val)

        return cookie

    def delete_cookie(
        self, key: str, path: str = "/", domain: str | None = None
    ) -> Any:
        """Delete a cookie by setting its expiration to the past.

        Sends a ``Set-Cookie`` header with an empty value and zero expiration,
        instructing the client to remove the specified cookie.  The path and
        domain must match those used when the cookie was originally set for
        the deletion to take effect.

        Args:
            key: The name of the cookie to delete.
            path: The URL path where the cookie was originally set.  Must
                match the original cookie's path.  Defaults to ``"/"``.
            domain: The domain where the cookie was originally set.  Must
                match the original cookie's domain.  Defaults to ``None``.

        Returns:
            The underlying ``SimpleCookie`` object for advanced manipulation.

        Raises:
            None: This method does not raise exceptions.
        """
        cookie = self.set_cookie(
            key=key, value="", max_age=0, expires=0, path=path, domain=domain
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
        self.set_header("content-length", str(len(self._body)), overide=True)
        return self

    def _generate_etag(self) -> str:
        """Generate an ETag for the response content."""
        content_hash = sha1()
        content_hash.update(self._body)
        return f'W/"{b64encode(content_hash.digest()).decode("utf-8")}"'

    def set_header(self, key: str, value: str, overide: bool = False) -> BaseResponse:
        """Set a response header.

        Args:
            key: Header name.
            value: Header value.
            overide: If True, replace existing header with same name.
        """
        key_bytes = key.lower().encode(
            "latin-1"
        )  # Normalize key to lowercase for case-insensitive comparison
        value_bytes = value.encode("latin-1")
        new_header = (key_bytes, value_bytes)

        if overide:
            # Edit in place rather than rebinding: `self.headers` caches a
            # MutableHeaders around this exact list, and a fresh list leaves
            # that cache pointing at an orphan, so later edits through
            # `response.headers` never reach the wire.
            self.raw_headers[:] = [
                (k, v) for k, v in self.raw_headers if k != key_bytes
            ]

        self.raw_headers.append(new_header)
        return self

    def set_headers(self, headers: dict[str, str], overide_all: bool = False):
        """Set multiple headers at once.

        Args:
            headers: Dict of header name to value.
            overide_all: If True, replace all existing headers.
        """
        if overide_all:
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
            # Pre-process content through jsonable_encoder when requested
            # to handle complex types (datetimes, UUIDs, Decimals, models, …)
            if use_encoder:
                from sillo.core.encoding import jsonable_encoder

                content = jsonable_encoder(content, custom_encoder=custom_encoder)

            body = json.dumps(
                content,
                indent=indent,
                ensure_ascii=ensure_ascii,
                allow_nan=False,
                default=str,
            )
        except (TypeError, ValueError) as e:
            raise ValueError(f"Content is not JSON serializable: {e!s}")

        super().__init__(
            body=body,
            status_code=status_code,
            headers=headers,
            content_type="application/json",
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

        self.set_header("content-length", content_length, overide=True)
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
            self.set_header("content-range", f"bytes */{file_size}", overide=True)
            # `set_stat_headers` declared the whole file. A 416 sends no body
            # at all, so leaving that in place promises bytes that never come
            # and the server tears the connection down mid-response.
            self.set_header("content-length", "0", overide=True)
            self.status_code = 416
            return

        self.status_code = 206

        if len(self._ranges) == 1:
            start, end = self._ranges[0]
            self.set_header(
                "content-range", f"bytes {start}-{end}/{file_size}", overide=True
            )
            self.set_header("content-length", str(end - start + 1), overide=True)
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
            overide=True,
        )
        self.set_header(
            "content-length", str(self._multipart_length(file_size)), overide=True
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


class Responder:
    """
    Fluent HTTP response builder for sillo framework.

    Responder provides a chainable, fluent interface for building HTTP responses
    with support for various content types, headers, cookies, caching, and more.
    It acts as a wrapper around the lower-level BaseResponse classes while providing
    a more convenient and intuitive API.

    Key Features:
    - Fluent/chainable API for building responses
    - Support for JSON, HTML, plain text, and file responses
    - Cookie management with security options
    - HTTP caching controls
    - Custom headers and status codes
    - File downloads and streaming responses
    - Pagination support for large datasets
    - Redirect responses

    Examples:
        1. JSON responses:
        ```python
        @app.get("/users")
        async def get_users(request: Request, response: Response):
            users = await get_all_users()
            return response.json(users)

        @app.post("/users")
        async def create_user(request: Request, response: Response):
            data = await request.json
            user = await create_user(data)
            return response.json(user, status=201)
        ```

        2. HTML responses:
        ```python
        @app.get("/")
        async def home(request: Request, response: Response):
            html_content = "<h1>Welcome to sillo!</h1>"
            return response.html(html_content)
        ```

        3. File responses:
        ```python
        @app.get("/download/{filename}")
        async def download_file(request: Request, response: Response):
            filename = request.path_params['filename']
            return response.download(f"files/{filename}")

        @app.get("/avatar/{user_id}")
        async def get_avatar(request: Request, response: Response):
            user_id = request.path_params['user_id']
            return response.file(f"avatars/{user_id}.jpg")
        ```

        4. Responses with headers and cookies:
        ```python
        @app.post("/login")
        async def login(request: Request, response: Response):
            data = await request.json
            user = await authenticate(data['username'], data['password'])

            if user:
                token = generate_jwt_token(user)
                return (response
                    .json({"message": "Login successful"})
                    .set_cookie("auth_token", token, httponly=True, secure=True)
                    .set_header("X-User-ID", str(user.id)))
            else:
                return response.json({"error": "Invalid credentials"}, status=401)
        ```

        5. Cached responses:
        ```python
        @app.get("/static-data")
        async def get_static_data(request: Request, response: Response):
            data = await get_expensive_computation()
            return (response
                .json(data)
                .cache(max_age=3600, private=False))  # Cache for 1 hour
        ```

        6. Streaming responses:
        ```python
        @app.get("/stream")
        async def stream_data(request: Request, response: Response):
            async def generate_data():
                for i in range(1000):
                    yield f"data chunk {i}\n"
                    await asyncio.sleep(0.1)

            return response.stream(generate_data(), content_type="text/plain")
        ```

        7. Paginated responses:
        ```python
        @app.get("/users")
        async def get_users(request: Request, response: Response):
            users = await get_all_users()
            return response.paginate(
                users,
                strategy="page_number",
                page_size=20
            )
        ```
    """

    def __init__(self, request: Request):
        self._response: BaseResponse | Any = None
        self._request = request

    @property
    def headers(self):
        return MutableHeaders(raw=self._response.raw_headers)

    @property
    def body(self):
        return self._response._body

    @property
    def content_type(self):
        return self._response.content_type

    @property
    def content_length(self):
        content_length = self.headers.get("content-length")
        if not content_length:
            return str(len(self.body))

        return content_length

    @property
    def status_code(self):
        return self._response.status_code

    def has_header(self, key: str) -> bool:
        """Check if a header is present in the response."""

        return key.lower() in (k.lower() for k in self.headers)

    def text(
        self,
        content: JSONType,
        status_code: int = 200,
        headers: dict[str, Any] = {},
    ):
        """Send plain text or HTML content."""
        new_response = PlainTextResponse(
            body=content, status_code=status_code, headers=headers
        )
        self._response = new_response
        return self

    def json(
        self,
        data: Annotated[
            str | list[Any] | dict[str, Any],
            Doc("""
                Data to serialize as JSON response.
                
                Can be any JSON-serializable Python object including:
                - Dictionaries and lists
                - Strings, numbers, booleans
                - Pydantic models (automatically serialized)
                - Custom objects with __dict__ or to_dict() methods
                
                Examples:
                - {"message": "Hello, World!"}
                - [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]
                - user_model.dict() for Pydantic models
                """),
        ],
        status_code: Annotated[
            int,
            Doc("""
                HTTP status code for the response.
                
                Common status codes:
                - 200: OK (default)
                - 201: Created (for successful POST requests)
                - 400: Bad Request
                - 404: Not Found
                - 500: Internal Server Error
                """),
        ] = 200,
        headers: Annotated[
            dict[str, Any],
            Doc("""
                Additional HTTP headers to include in the response.
                
                Example: {"X-Custom-Header": "value", "Cache-Control": "no-cache"}
                """),
        ] = {},
        indent: Annotated[
            int | None,
            Doc("""
                Number of spaces to use for JSON indentation.
                
                - None: Compact JSON (default)
                - 2 or 4: Pretty-printed JSON for debugging
                """),
        ] = None,
        ensure_ascii: Annotated[
            bool,
            Doc("""
                Whether to escape non-ASCII characters in JSON output.
                
                - True: Escape non-ASCII characters (default)
                - False: Allow Unicode characters in output
                """),
        ] = True,
        custom_encoder: Annotated[
            dict[type, Callable[[Any], Any]] | None,
            Doc("""
                One-off custom type encoders applied only to this response.
                
                Mapping of Python type to a callable that converts an instance
                of that type into a JSON-serializable value. These are merged
                on top of any encoders registered via ``app.add_encoder``.
                
                Example: {Decimal: lambda d: float(d)}
                """),
        ] = None,
    ):
        """
        Send a JSON response with the provided data.

        This method serializes the provided data to JSON and sets the appropriate
        Content-Type header. It supports pretty-printing for development and
        handles various Python data types automatically.

        Returns:
            Responder: Self for method chaining

        Examples:
            1. Simple JSON response:
            ```python
            return response.json({"message": "Hello, World!"})
            ```

            2. JSON with custom status:
            ```python
            return response.json({"error": "Not found"}, status=404)
            ```

            3. Pretty-printed JSON for debugging:
            ```python
            return response.json(data, indent=2)
            ```

            4. JSON with custom headers:
            ```python
            return response.json(
                data,
                headers={"X-Total-Count": str(len(data))}
            )
            ```
        """

        new_response = JSONResponse(
            content=data,
            headers=headers,
            status_code=status_code,
            indent=indent,
            ensure_ascii=ensure_ascii,
            custom_encoder=custom_encoder,
        )
        self._response = new_response
        return self

    def download(self, path: str, filename: str | None = None) -> Responder:
        """Set a response to force a file download."""
        return self.file(path, filename, content_disposition_type="attachment")

    def set_permanent_cookie(self, key: str, value: str, **kwargs: Any) -> Responder:
        """Set a permanent cookie with a far-future expiration date."""
        expires = datetime.now(timezone.utc) + timedelta(days=365 * 10)
        self.set_cookie(key, value, expires=expires, **kwargs)
        return self

    def empty(self, status_code: int = 200, headers: dict[str, Any] = {}):
        """Send an empty response."""

        new_response = BaseResponse(status_code=status_code, headers=headers)
        self._response = new_response
        return self

    def abort(
        self,
        status_code: int,
        detail: typing.Any | None = None,
        headers: dict[str, Any] = {},
    ) -> typing.NoReturn:
        """
        Abort the request by raising an :class:`HTTPException`.

        Unlike the other builder methods, ``abort`` does **not** return a
        response. It raises immediately so the framework's exception middleware
        can render a consistent error envelope (JSON by default, HTML/JSON for
        404 via the registered handlers). Use it inside a handler when you want
        to short-circuit with an error status instead of returning a body.

        Args:
            status_code: HTTP status code for the error (e.g. 400, 401, 403).
            detail: Optional error detail / message. Rendered by the handler.
            headers: Optional headers attached to the raised exception.

        Raises:
            HTTPException: Always, with the given status code and detail.

        Examples:
            ```python
            @app.get("/admin")
            async def admin(request, response):
                if not request.user.is_admin:
                    response.abort(403, detail="Admins only")
                return response.json({"ok": True})
            ```
        """
        raise HTTPException(status_code=status_code, detail=detail, headers=headers)

    def not_found(
        self,
        detail: str | None = None,
        headers: dict[str, Any] = {},
    ) -> typing.NoReturn:
        """
        Abort the request with a 404 by raising a :class:`NotFoundException`.

        Convenience shorthand for ``response.abort(404, detail=...)``. The
        framework renders it through the registered 404 handler, which supports
        JSON, HTML, and plain-text responses based on configuration.

        Args:
            detail: Optional message describing what was not found.
            headers: Optional headers attached to the raised exception.

        Raises:
            NotFoundException: Always, with status code 404.

        Examples:
            ```python
            @app.get("/items/{item_id}")
            async def get_item(request, response):
                item = await db.get(item_id)
                if item is None:
                    response.not_found(detail=f"Item {item_id} not found")
                return response.json(item)
            ```
        """
        raise NotFoundException(detail=detail, headers=headers)

    def html(
        self,
        content: str,
        status_code: int = 200,
        headers: dict[str, Any] = {},
    ):
        """Send HTML response."""

        new_response = HTMLResponse(
            content=content, status_code=status_code, headers=headers
        )
        self._response = new_response
        return self

    def file(
        self,
        path: str,
        filename: str | None = None,
        content_disposition_type: str = "inline",
        status_code: int = 200,
        headers: dict[str, Any] = {},
    ):
        """Send file response."""
        new_response = FileResponse(
            path=path,
            filename=filename,
            status_code=status_code,
            headers=headers,
            content_disposition_type=content_disposition_type,
        )
        self._response = new_response
        return self

    def stream(
        self,
        iterator: AsyncIterator[str | bytes],
        content_type: str = "text/plain",
        status_code: int = 200,
        headers: dict[str, Any] = {},
    ):
        """Send streaming response."""

        new_response = StreamingResponse(
            content=iterator,
            status_code=status_code,
            headers=headers,
            content_type=content_type,
        )
        self._response = new_response
        return self

    def sse(
        self,
        source: AsyncIterable[Any],
        *,
        keepalive: float | None = 15.0,
        ping: str = "ping",
        retry: int | None = None,
        encoder: typing.Callable[[Any], str] | None = None,
        status_code: int = 200,
        headers: dict[str, Any] | None = None,
    ):
        """Send a Server-Sent Events stream.

        Yield a ``dict`` (JSON-encoded), a ``str`` (sent as-is), or a
        :class:`~sillo.http.sse.ServerSentEvent` for control over the event
        name, id and reconnection delay::

            @app.get("/events")
            async def events(request: Request, response: Response):
                async def source():
                    while True:
                        yield {"price": await next_tick()}

                return response.sse(source())

        Args:
            source: An async iterable of events.
            keepalive: Seconds of silence after which a comment line is sent to
                stop an idle connection being closed by a proxy. None disables
                it. The default is below the 60s that nginx and most load
                balancers use for ``proxy_read_timeout``.
            ping: Comment text used for the keepalive.
            retry: Reconnection delay in milliseconds, sent once at the start.
                ``EventSource`` remembers it across reconnects.
            encoder: Applied to non-string payloads. Defaults to ``json.dumps``.
            status_code: Response status.
            headers: Extra headers, merged over the defaults below.

        Returns:
            This responder, for chaining.

        Note:
            Three headers are set that a plain ``stream`` would not. ``no-cache``
            keeps the response out of caches; ``no-transform`` stops a proxy
            re-encoding it; and ``x-accel-buffering: no`` disables nginx's
            response buffering, without which events are held back and delivered
            in batches rather than as they happen. Pass them in ``headers`` to
            override any of it.
        """
        from sillo.http.sse import sse_stream

        options: dict[str, Any] = {"keepalive": keepalive, "ping": ping, "retry": retry}
        if encoder is not None:
            options["encoder"] = encoder

        merged: dict[str, Any] = {
            "cache-control": "no-cache, no-transform",
            "connection": "keep-alive",
            "x-accel-buffering": "no",
        }
        merged.update(headers or {})

        return self.stream(
            sse_stream(source, **options),
            content_type="text/event-stream",
            status_code=status_code,
            headers=merged,
        )

    def redirect(
        self,
        url: str | None = None,
        name: str | None = None,
        status_code: int = 302,
        headers: dict[str, Any] = {},
        **path_params: typing.Any,
    ):
        """
        Send redirect response.

        Can use either a URL or a route name. When using name, path_params
        are passed to url_for() to generate the URL.

        Args:
            url: Direct URL to redirect to
            name: Route name to redirect to (uses url_for to generate URL)
            status_code: HTTP status code (default 302 Found)
            headers: Additional headers to include
            **path_params: Path parameters for URL generation when using name
        """
        request = self._request
        if url is None and name is None:
            raise ValueError("Either 'url' or 'name' must be provided")
        if url is not None and name is not None:
            raise ValueError("Cannot provide both 'url' and 'name'")

        if name is not None:
            app = self._get_base_app()
            url_path = app.url_for(name, **path_params)
            url = str(request.base_url) + str(url_path)

        if url is None:
            raise ValueError("URL is required for redirect")

        new_response = RedirectResponse(
            url=url, status_code=status_code, headers=headers
        )
        self._response = new_response
        return self

    def _get_base_app(self) -> typing.Any:
        if hasattr(self, "_base_app"):
            return self._base_app
        if hasattr(self, "_request"):
            self._base_app = self._request.scope.get("base_app")
            return self._base_app
        raise RuntimeError("Could not access base app for URL generation")

    def status(self, status_code: int):
        """Set response status code."""
        if not self._response:
            self.empty()
        self._response.status_code = status_code
        return self

    def set_header(self, key: str, value: str, overide: bool = False):
        """Set a response header."""
        self._response.set_header(key, value, overide=overide)
        return self

    def set_cookie(
        self,
        key: Annotated[str, Doc("Name of the cookie to set")],
        value: Annotated[str, Doc("Value to store in the cookie")],
        max_age: Annotated[
            int | None,
            Doc("""
                Maximum age of the cookie in seconds.
                
                If set, the cookie will expire after this many seconds.
                Takes precedence over 'expires' if both are set.
                
                Examples:
                - 3600: Cookie expires in 1 hour
                - 86400: Cookie expires in 1 day
                - 604800: Cookie expires in 1 week
                """),
        ] = None,
        expires: Annotated[
            str | datetime | int | None,
            Doc("""
                Expiration date/time for the cookie.
                
                Can be:
                - datetime object: Specific expiration time
                - int: Unix timestamp
                - str: HTTP date string
                
                Example: datetime.now() + timedelta(days=7)
                """),
        ] = None,
        path: Annotated[
            str,
            Doc("""
                URL path where the cookie is valid.
                
                - "/" (default): Cookie valid for entire domain
                - "/admin": Cookie only valid for admin section
                """),
        ] = "/",
        domain: Annotated[
            str | None,
            Doc("""
                Domain where the cookie is valid.
                
                - None (default): Cookie valid for current domain only
                - ".example.com": Cookie valid for all subdomains
                """),
        ] = None,
        secure: Annotated[
            bool,
            Doc("""
                Whether cookie should only be sent over HTTPS.
                
                - True (default): Cookie only sent over secure connections
                - False: Cookie sent over HTTP and HTTPS
                
                Recommended to keep True for production.
                """),
        ] = True,
        httponly: Annotated[
            bool,
            Doc("""
                Whether cookie should be inaccessible to JavaScript.
                
                - True: Cookie cannot be accessed via document.cookie
                - False (default): Cookie accessible to JavaScript
                
                Set to True for authentication cookies to prevent XSS attacks.
                """),
        ] = False,
        samesite: Annotated[
            typing.Literal["lax", "strict", "none"] | None,
            Doc("""
                SameSite attribute for CSRF protection.
                
                - "lax" (default): Cookie sent with same-site requests and top-level navigation
                - "strict": Cookie only sent with same-site requests
                - "none": Cookie sent with all requests (requires secure=True)
                """),
        ] = "lax",
    ):
        """
        Set an HTTP cookie in the response.

        Cookies are used to store small pieces of data in the client's browser
        that are sent back with subsequent requests. This method provides full
        control over cookie attributes for security and functionality.

        Returns:
            Responder: Self for method chaining

        Examples:
            1. Simple session cookie:
            ```python
            return response.set_cookie("session_id", session_token)
            ```

            2. Secure authentication cookie:
            ```python
            return response.set_cookie(
                "auth_token",
                jwt_token,
                max_age=3600,  # 1 hour
                httponly=True,  # Prevent XSS
                secure=True,    # HTTPS only
                samesite="strict"  # CSRF protection
            )
            ```

            3. Remember me cookie:
            ```python
            return response.set_cookie(
                "remember_token",
                token,
                max_age=30*24*3600,  # 30 days
                httponly=True,
                secure=True
            )
            ```

            4. User preference cookie:
            ```python
            return response.set_cookie(
                "theme",
                "dark",
                max_age=365*24*3600,  # 1 year
                secure=False,  # Accessible to JavaScript
                samesite="lax"
            )
            ```
        """
        self._response.set_cookie(
            key=key,
            value=value,
            max_age=max_age,
            expires=expires,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )
        return self

    def delete_cookie(
        self,
        key: str,
        path: str = "/",
        domain: str | None = None,
    ):
        """Delete a response cookie."""
        self._response.delete_cookie(
            key=key,
            path=path,
            domain=domain,
        )

        return self

    def cache(self, max_age: int = 3600, private: bool = True):
        """Enable response caching."""
        self._response.enable_caching(max_age, private)
        return self

    def no_cache(self):
        """Disable response caching."""
        self._response.disable_caching()
        return self

    def resp(
        self,
        body: JSONType | Any = "",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content_type: str = "text/plain",
    ):
        """
        Provides access to the purest form of the response object.
        """
        new_response = BaseResponse(
            body=body,
            status_code=status_code,
            headers=headers,
            content_type=content_type,
        )
        self._response = new_response
        return self

    def set_cookies(self, cookies: list[dict[str, Any]]):
        """Set multiple cookies at once."""
        for cookie in cookies:
            self.set_cookie(**cookie)
        return self

    def set_headers(self, headers: dict[str, str], overide_all: bool = False):
        """Set multiple headers at once."""
        if overide_all:
            self._response.set_headers(headers)
            return self
        for key, value in headers.items():
            self.set_header(key, value)
        return self

    def set_body(self, new_body: Any):
        if not self._response:
            return self.resp(new_body)
        self._response.set_body(new_body)
        return self

    def get_response(self) -> BaseResponse:
        """Make the response ASGI-compatible."""
        return self._response

    def add_csp_header(self, policy: str) -> Responder:
        """Add a Content Security Policy header."""
        self.set_header("Content-Security-Policy", policy)
        return self

    def make_response(self, response_class: BaseResponse) -> Responder:
        """
        Create a response using a custom response class.

        Args:
            response_class (Type[BaseResponse]): The custom response class to use.
            *args: Positional arguments to pass to the custom response class.
            **kwargs: Keyword arguments to pass to the custom response class.

        Returns:
            Responder: The current instance for method chaining.
        """

        self._response = response_class
        return self

    def remove_header(self, key: str):
        """Remove a header from the response."""
        self._response.remove_header(key)

    def paginate(
        self,
        objects: list[Any],
        strategy: str | BasePaginationStrategy = "page_number",
        data_handler: type[SyncListDataHandler] = SyncListDataHandler,
        **kwargs: Any,
    ) -> Responder:
        """
        Paginate the response data.

        Args:
            objects: List of items to paginate
            strategy: Either a string ('page_number', 'limit_offset', 'cursor') or
                    a custom pagination strategy instance
            **kwargs: Additional arguments for the pagination strategy or parameter overrides
        """
        if isinstance(strategy, str):
            # Define known configuration keys for strategies to separate them from parameter overrides
            config_keys = {
                "page_param",
                "page_size_param",
                "default_page",
                "default_page_size",
                "max_page_size",
                "limit_param",
                "offset_param",
                "default_limit",
                "max_limit",
                "cursor_param",
                "sort_field",
            }
            strategy_kwargs = {k: v for k, v in kwargs.items() if k in config_keys}

            if strategy == "page_number":
                strategy = PageNumberPagination(**strategy_kwargs)
            elif strategy == "limit_offset":
                strategy = LimitOffsetPagination(**strategy_kwargs)
            elif strategy == "cursor":
                strategy = CursorPagination(**strategy_kwargs)
            else:
                raise ValueError(f"Unknown pagination strategy: {strategy}")

        _data_handler = data_handler(objects)
        request = self._request

        paginator = SyncPaginator(
            data_handler=_data_handler,
            pagination_strategy=strategy,
            base_url=str(request.url),
            request_params=dict(request.query_params),
        )

        result = paginator.paginate(**kwargs)
        return self.json(result)

    async def apaginate(
        self,
        objects: list[Any],
        strategy: str | BasePaginationStrategy = "page_number",
        data_handler: type[AsyncListDataHandler] = AsyncListDataHandler,
        **kwargs: Any,
    ) -> Responder:
        """
        Paginate the response data asynchronously.

        Args:
            objects: List of items to paginate
            strategy: Either a string ('page_number', 'limit_offset', 'cursor') or
                    a custom pagination strategy instance
            **kwargs: Additional arguments for the pagination strategy or parameter overrides
        """
        if isinstance(strategy, str):
            # Define known configuration keys for strategies to separate them from parameter overrides
            config_keys = {
                "page_param",
                "page_size_param",
                "default_page",
                "default_page_size",
                "max_page_size",
                "limit_param",
                "offset_param",
                "default_limit",
                "max_limit",
                "cursor_param",
                "sort_field",
            }
            strategy_kwargs = {k: v for k, v in kwargs.items() if k in config_keys}

            if strategy == "page_number":
                strategy = PageNumberPagination(**strategy_kwargs)
            elif strategy == "limit_offset":
                strategy = LimitOffsetPagination(**strategy_kwargs)
            elif strategy == "cursor":
                strategy = CursorPagination(**strategy_kwargs)
            else:
                raise ValueError(f"Unknown pagination strategy: {strategy}")

        _data_handler = data_handler(objects)
        request = self._request

        paginator = AsyncPaginator(
            data_handler=_data_handler,
            pagination_strategy=strategy,
            base_url=str(request.url),
            request_params=dict(request.query_params),
        )

        result = await paginator.paginate(**kwargs)
        return self.json(result)

    async def __call__(self, *args: Any, **kwargs: Any):

        return await self._response(*args, **kwargs)

    def __str__(self):
        return f"Response [{self.status_code} {self.body}]"
