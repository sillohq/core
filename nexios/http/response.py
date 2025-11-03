import hashlib
import http.cookies
import json
import mimetypes
import os
import stat
import typing
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, formatdate
from functools import partial
from hashlib import sha1
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Generator, List, Optional, Tuple, Union
from urllib.parse import quote

import anyio
import anyio.to_thread
from anyio import AsyncFile

from nexios.http.request import ClientDisconnect, Request
from nexios.pagination import (
    AsyncListDataHandler,
    AsyncPaginator,
    BasePaginationStrategy,
    CursorPagination,
    LimitOffsetPagination,
    PageNumberPagination,
    SyncListDataHandler,
    SyncPaginator,
)
from nexios.structs import MutableHeaders

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]

JSONType = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]


class MalformedRangeHeader(Exception):
    def __init__(self, content: str = "Malformed range header.") -> None:
        self.content = content


class RangeNotSatisfiable(Exception):
    def __init__(self, max_size: int) -> None:
        self.max_size = max_size


class BaseResponse:
    """
    Base ASGI-compatible Response class with support for cookies, caching, and custom headers.
    """

    STATUS_CODES = {
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
        body: Union[JSONType, Any] = "",
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
    ):
        self.charset = "utf-8"
        self.status_code: int = status_code
        self._headers: List[Tuple[bytes, bytes]] = []
        self._body = self.render(body)
        self.headers = headers or {}

        self.content_type: typing.Optional[str] = content_type

    def render(self, content: typing.Any) -> typing.Union[bytes, memoryview]:
        if content is None:
            return b""
        if isinstance(content, (bytes, memoryview)):
            return content  # type: ignore
        return content.encode(self.charset)  # type: ignore

    def _init_headers(self):
        raw_headers = [
            (k.lower().encode("latin-1"), v.encode("latin-1"))
            for k, v in self.headers.items()
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
        content_type: typing.Optional[str] = self.content_type
        if content_type is not None and populate_content_type:
            if (
                content_type.startswith("text/")
                and "charset=" not in content_type.lower()
            ):
                content_type += "; charset=" + self.charset
            self._headers.append((b"content-type", content_type.encode("latin-1")))

        self._headers.extend(raw_headers)

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: typing.Optional[int] = None,
        expires: typing.Union[datetime, str, int, None] = None,
        path: typing.Optional[str] = "/",
        domain: typing.Optional[str] = None,
        secure: typing.Optional[bool] = False,
        httponly: typing.Optional[bool] = False,
        samesite: typing.Optional[typing.Literal["lax", "strict", "none"]] = "lax",
    ) -> Any:
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
        self, key: str, path: str = "/", domain: Optional[str] = None
    ) -> Any:
        """Delete a cookie by setting its expiry to the past."""
        cookie = self.set_cookie(
            key=key, value="", max_age=0, expires=0, path=path, domain=domain
        )

        return cookie

    def enable_caching(self, max_age: int = 3600, private: bool = True) -> None:
        """Enable caching with the specified max age (in seconds)."""
        cache_control: List[str] = []
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
        self._init_headers()
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self._headers + scope.get("pre-response-headers", []),
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
        return self._body

    @property
    def raw_headers(self):
        return self._headers

    def _generate_etag(self) -> str:
        """Generate an ETag for the response content."""
        content_hash = sha1()
        content_hash.update(self._body)  # type:ignore
        return f'W/"{b64encode(content_hash.digest()).decode("utf-8")}"'

    def set_header(self, key: str, value: str, overide: bool = False) -> "BaseResponse":
        """
        Set a response header. If `overide` is True, replace the existing header.
        """
        key_bytes = key.lower().encode(
            "latin-1"
        )  # Normalize key to lowercase for case-insensitive comparison
        value_bytes = value.encode("latin-1")
        new_header = (key_bytes, value_bytes)

        if overide:
            self._headers = [(k, v) for k, v in self._headers if k != key_bytes]

        self._headers.append(new_header)
        return self

    def set_headers(self, headers: Dict[str, str], overide_all: bool = False):
        if overide_all:
            self._headers = [
                (k.lower().encode("latin-1"), v.encode("latin-1"))
                for k, v in headers.items()
            ]
            return
        """Set multiple headers at once."""
        for key, value in headers.items():
            self.set_header(key, value)
        return self


class PlainTextResponse(BaseResponse):
    def __init__(
        self,
        body: JSONType = "",
        status_code: int = 200,
        headers: typing.Optional[Dict[str, str]] = None,
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
        headers: Optional[Dict[str, str]] = None,
        indent: Optional[int] = None,
        ensure_ascii: bool = True,
    ):
        try:
            body = json.dumps(
                content,
                indent=indent,
                ensure_ascii=ensure_ascii,
                allow_nan=False,
                default=str,
            )
        except (TypeError, ValueError) as e:
            raise ValueError(f"Content is not JSON serializable: {str(e)}")

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
        content: Union[str, JSONType],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
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
        path: Union[str, Path],
        filename: Optional[str] = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        content_disposition_type: str = "inline",
    ):
        super().__init__(headers=headers)
        self.path = Path(path)
        self.filename = filename or self.path.name
        self.content_disposition_type = content_disposition_type
        self.status_code = status_code

        self.headers = headers or {}
        content_type, _ = mimetypes.guess_type(str(self.path))
        self.set_header("content-type", content_type or "application/octet-stream")
        self.set_header(
            "content-disposition",
            f'{content_disposition_type}; filename="{self.filename}"',
        )
        self.set_header("accept-ranges", "bytes")

        self._ranges: List[Tuple[int, int]] = []
        self._multipart_boundary: Optional[str] = None

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

    def _handle_range_header(self, range_header: str) -> None:
        """Parse and validate the Range header."""
        file_size = self.path.stat().st_size

        try:
            unit, ranges = range_header.strip().split("=")
            if unit != "bytes":
                raise ValueError("Only byte ranges are supported")

            self._ranges = []
            for range_str in ranges.split(","):
                range = range_str.split("-")
                start: int = int(range[0])
                end: int = int(range[-1]) if range[-1] != "" else 0  # type: ignore
                start = int(start) if start else 0
                end: int = int(end) if end else file_size - 1

                if start < 0 or end >= file_size or start > end:
                    raise ValueError("Invalid range")

                self._ranges.append((start, end))

            if len(self._ranges) == 1:
                start, end = self._ranges[0]
                content_length = end - start + 1
                self.set_header("content-range", f"bytes {start}-{end}/{file_size}")
                self.set_header("content-length", str(content_length), overide=True)
                self.status_code = 206
            elif len(self._ranges) > 1:
                self._multipart_boundary = self._generate_multipart_boundary()
                self.set_header(
                    "content-type",
                    f"multipart/byteranges; boundary={self._multipart_boundary}",
                )
                self.status_code = 206

        except ValueError as _:
            self.set_header("content-range", f"bytes */{file_size}")
            self.status_code = 416

    async def _send_response(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send the file response, handling range requests and multipart responses."""

        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self._headers,
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
                for start, end in self._ranges:
                    await self._send_multipart_chunk(file, start, end, send)
                await send(
                    {
                        "type": "http.response.body",
                        "body": f"--{self._multipart_boundary}--\r\n".encode("utf-8"),
                        "more_body": False,
                    }
                )
            elif self._ranges:
                start, end = self._ranges[0]
                await self._send_range(file, start, end, send)  # type:ignore
            else:
                await self._send_full_file(file, send)  # type:ignore

    async def _send_full_file(self, file: AsyncIterator[bytes], send: Send) -> None:
        """Send the entire file in chunks using AnyIO."""
        while True:
            chunk = await file.read(self.chunk_size)  # type:ignore
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
        remaining = end - start + 1
        self.set_header("content-length", str(remaining), overide=True)

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
        self, file: AsyncFile[bytes], start: int, end: int, send: Send
    ) -> None:
        """Send a multipart chunk for a range using AnyIO."""
        await file.seek(start)
        remaining = end - start + 1

        boundary = f"--{self._multipart_boundary}\r\n"
        header = next(
            (value for key, value in self._headers if key == b"content-type"), None
        )
        headers = f"Content-Type: {header}\r\nContent-Range: bytes {start}-{end}/{self.path.stat().st_size}\r\n\r\n"  # type:ignore[str-bytes-safe]
        await send(
            {
                "type": "http.response.body",
                "body": (boundary + headers).encode("utf-8"),
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

    def _generate_multipart_boundary(self) -> str:
        """Generate a unique multipart boundary string."""
        return f"boundary_{os.urandom(16).hex()}"


class StreamingResponse(BaseResponse):
    """
    Response subclass for streaming content.
    """

    def __init__(
        self,
        content: AsyncIterator[Union[str, bytes]],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        content_type: str = "text/plain",
    ):
        super().__init__(headers=headers)

        self.content_iterator = content
        self.status_code = status_code
        self._cookies: List[Tuple[str, str, Dict[str, Any]]] = []

        self.content_type = content_type
        self.headers["content-type"] = self.content_type

        self.headers.pop("content-length", None)
        self._headers += [
            (k.lower().encode("latin-1"), v.encode("latin-1"))
            for k, v in self.headers.items()
        ]

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
                chunk = chunk.encode(self.charset)  # type:ignore

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
        headers: Dict[str, str] = {},
    ):
        if not 300 <= status_code < 400:
            raise ValueError("Status code must be a valid redirect status")

        headers["location"] = quote(str(url), safe=":/%#?=@[]!$&'()*+,;")

        super().__init__(body="", status_code=status_code, headers=headers)


class NexiosResponse:
    _instance = None

    def __new__(cls, *args, **kwargs):  # type:ignore
        if cls._instance is None:
            cls._instance = super(NexiosResponse, cls).__new__(cls)
            cls._instance._initialized = False  # type:ignore
        return cls._instance

    def __init__(self, request: Request):
        self._response: BaseResponse = BaseResponse()
        self._cookies: List[Dict[str, Any]] = []
        self._status_code = self._response.status_code
        self._request = request

    @property
    def headers(self):
        return MutableHeaders(raw=self._response._headers)  # type:ignore

    @property
    def cookies(self):
        return self._cookies  # type:ignore

    @property
    def body(self):
        return self._response._body  # type:ignore

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

    def _preserve_headers_and_cookies(self, new_response: BaseResponse) -> BaseResponse:
        """Preserve headers and cookies when switching to a new response."""
        for key, value in self.headers.items():
            new_response.set_header(key, value)

        return new_response

    def has_header(self, key: str) -> bool:
        """Check if a header is present in the response."""
        return key.lower() in (k.lower() for k in self.headers.keys())

    def text(
        self,
        content: JSONType,
        status_code: Optional[int] = None,
        headers: Dict[str, Any] = {},
    ):
        """Send plain text or HTML content."""
        if status_code is None:
            status_code = self._status_code
        new_response = PlainTextResponse(
            body=content, status_code=status_code, headers=headers
        )
        self._response = self._preserve_headers_and_cookies(new_response)
        return self

    def json(
        self,
        data: Union[str, List[Any], Dict[str, Any]],
        status_code: Optional[int] = None,
        headers: Dict[str, Any] = {},
        indent: Optional[int] = None,
        ensure_ascii: bool = True,
    ):
        """Send JSON response."""
        if status_code is None:
            status_code = self._status_code
        new_response = JSONResponse(
            content=data,
            status_code=status_code,
            headers=headers,
            indent=indent,
            ensure_ascii=ensure_ascii,
        )
        self._response = self._preserve_headers_and_cookies(new_response)
        return self

    def download(self, path: str, filename: Optional[str] = None) -> "NexiosResponse":
        """Set a response to force a file download."""
        return self.file(path, filename, content_disposition_type="attachment")

    def set_permanent_cookie(
        self, key: str, value: str, **kwargs: Dict[str, Any]
    ) -> "NexiosResponse":
        """Set a permanent cookie with a far-future expiration date."""
        expires = datetime.now(timezone.utc) + timedelta(days=365 * 10)
        self.set_cookie(key, value, expires=expires, **kwargs)  # type:ignore
        return self

    def empty(self, status_code: Optional[int] = None, headers: Dict[str, Any] = {}):
        """Send an empty response."""
        if status_code is None:
            status_code = self._status_code
        new_response = BaseResponse(status_code=status_code, headers=headers)
        self._response = self._preserve_headers_and_cookies(new_response)
        return self

    def html(
        self,
        content: str,
        status_code: Optional[int] = None,
        headers: Dict[str, Any] = {},
    ):
        """Send HTML response."""
        if status_code is None:
            status_code = self._status_code
        new_response = HTMLResponse(
            content=content, status_code=status_code, headers=headers
        )
        self._response = self._preserve_headers_and_cookies(new_response)
        return self

    def file(
        self,
        path: str,
        filename: Optional[str] = None,
        content_disposition_type: str = "inline",
    ):
        """Send file response."""
        new_response = FileResponse(
            path=path,
            filename=filename,
            status_code=self._status_code,
            headers=self._response.headers,
            content_disposition_type=content_disposition_type,
        )
        self._response = self._preserve_headers_and_cookies(new_response)
        self._response.status_code = self._status_code
        return self

    def stream(
        self,
        iterator: Generator[Union[str, bytes], Any, Any],
        content_type: str = "text/plain",
        status_code: Optional[int] = None,
    ):
        """Send streaming response."""
        if status_code is None:
            status_code = self._status_code
        new_response = StreamingResponse(
            content=iterator,  # type: ignore
            status_code=status_code or self._status_code,
            headers=self._response.headers,
            content_type=content_type,
        )
        self._response = self._preserve_headers_and_cookies(new_response)
        return self

    def redirect(self, url: str, status_code: int = 302):
        """Send redirect response."""
        new_response = RedirectResponse(
            url=url, status_code=status_code, headers=self._response.headers
        )
        self._response = self._preserve_headers_and_cookies(new_response)
        return self

    def status(self, status_code: int):
        """Set response status code."""
        self._response.status_code = status_code
        self._status_code = status_code
        return self

    def set_header(self, key: str, value: str, overide: bool = False):
        """Set a response header."""
        self._response.set_header(key, value, overide=overide)
        return self

    def set_cookie(
        self,
        key: str,
        value: str,
        max_age: Optional[int] = None,
        expires: Optional[Union[str, datetime, int]] = None,
        path: str = "/",
        domain: Optional[str] = None,
        secure: bool = True,
        httponly: bool = False,
        samesite: typing.Optional[typing.Literal["lax", "strict", "none"]] = "lax",
    ):
        """Set a response cookie."""
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
        domain: Optional[str] = None,
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
        body: Union[JSONType, Any] = "",
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
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
        self._response = self._preserve_headers_and_cookies(new_response)
        return self

    def set_cookies(self, cookies: List[Dict[str, Any]]):
        """Set multiple cookies at once."""
        for cookie in cookies:
            self.set_cookie(**cookie)
        return self

    def set_headers(self, headers: Dict[str, str], overide_all: bool = False):
        if overide_all:
            self._response.set_headers(headers)
            self._response._headers = [  # type:ignore
                (bytes(str(k), "utf-8"), bytes(str(v), "utf-8"))
                for k, v in self.headers.items()
            ]  # type:ignore
            return
        """Set multiple headers at once."""
        for key, value in headers.items():
            self.set_header(key, value)
        return self

    def set_body(self, new_body: Any):
        self._response._body = new_body  # type:ignore

    def get_response(self) -> BaseResponse:
        """Make the response ASGI-compatible."""
        return self._response

    def add_csp_header(self, policy: str) -> "NexiosResponse":
        """Add a Content Security Policy header."""
        self.set_header("Content-Security-Policy", policy)
        return self

    def make_response(self, response_class: BaseResponse) -> "NexiosResponse":
        """
        Create a response using a custom response class.

        Args:
            response_class (Type[BaseResponse]): The custom response class to use.
            *args: Positional arguments to pass to the custom response class.
            **kwargs: Keyword arguments to pass to the custom response class.

        Returns:
            NexiosResponse: The current instance for method chaining.
        """

        self._response = self._preserve_headers_and_cookies(response_class)
        return self

    def remove_header(self, key: str):
        """Remove a header from the response."""
        self._response._headers = [  # type:ignore
            (k, v)
            for k, v in self._response._headers  # type:ignore
            if k.decode("latin-1").lower() != key.lower()
        ]  # type:ignore

    def paginate(
        self,
        objects: List[Any],
        strategy: Union[str, BasePaginationStrategy] = "page_number",
        data_handler: type[SyncListDataHandler] = SyncListDataHandler,
        **kwargs: Dict[str, Any],
    ) -> "NexiosResponse":
        """
        Paginate the response data.

        Args:
            objects: List of items to paginate
            total_items: Total number of items (optional, defaults to len(items))
            strategy: Either a string ('page_number', 'limit_offset', 'cursor') or
                    a custom pagination strategy instance
            **kwargs: Additional arguments for the pagination strategy
        """
        if isinstance(strategy, str):
            if strategy == "page_number":
                strategy = PageNumberPagination(**kwargs)  # type:ignore
            elif strategy == "limit_offset":
                strategy = LimitOffsetPagination(**kwargs)  # type:ignore
            elif strategy == "cursor":
                strategy = CursorPagination(**kwargs)  # type:ignore
            else:
                raise ValueError(f"Unknown pagination strategy: {strategy}")

        _data_handler = data_handler(objects)
        request = self._request  # You'll need to store the request in the response

        paginator = SyncPaginator(
            data_handler=_data_handler,
            pagination_strategy=strategy,
            base_url=str(request.url),
            request_params=dict(request.query_params),
        )

        result = paginator.paginate()
        return self.json(result)

    async def apaginate(
        self,
        objects: List[Any],
        strategy: Union[str, BasePaginationStrategy] = "page_number",
        data_handler: type[AsyncListDataHandler] = AsyncListDataHandler,
        **kwargs: Dict[str, Any],
    ) -> "NexiosResponse":
        """
        Paginate the response data.

        Args:
            objects: List of items to paginate
            total_items: Total number of items (optional, defaults to len(items))
            strategy: Either a string ('page_number', 'limit_offset', 'cursor') or
                    a custom pagination strategy instance
            **kwargs: Additional arguments for the pagination strategy
        """
        if isinstance(strategy, str):
            if strategy == "page_number":
                strategy = PageNumberPagination(**kwargs)  # type:ignore
            elif strategy == "limit_offset":
                strategy = LimitOffsetPagination(**kwargs)  # type:ignore
            elif strategy == "cursor":
                strategy = CursorPagination(**kwargs)  # type:ignore
            else:
                raise ValueError(f"Unknown pagination strategy: {strategy}")

        _data_handler = data_handler(objects)
        request = self._request  # You'll need to store the request in the response

        paginator = AsyncPaginator(
            data_handler=_data_handler,
            pagination_strategy=strategy,
            base_url=str(request.url),
            request_params=dict(request.query_params),
        )

        result = await paginator.paginate()
        return self.json(result)

    def __str__(self):
        return f"Response [{self._status_code} {self.body}]"


Response = BaseResponse
