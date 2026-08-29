"""Every way to answer a request.

Sillo v1 has no request-scoped response manager. A handler builds its reply by
calling one of these and returning it; middleware ends the chain early the same
way. Each returns a plain :class:`~sillo.core.http.response.BaseResponse`
subclass, so what comes back *is* the response -- there is no wrapper to unwrap
and nothing to mutate through::

    from sillo.responses import json, redirect

    def show(ctx, id: int):
        return json({"id": id})

    async def gate(ctx, call_next):
        if ctx.user is None:
            return redirect("/login")      # break the chain
        return await call_next()

Everything the response itself owns -- status, headers, cookies, caching --
lives on the object, and each of those returns it again so they chain::

    return json(payload, status_code=201).set_cookie("seen", "1").cache(60)

The whole module is re-exported from ``sillo`` for the common ones, so
``from sillo import json`` and ``from sillo.responses import json`` are the same
function. Import from here when a module also needs the stdlib ``json``,
``html`` or the ``file`` builtin -- ``from sillo import responses`` then
``responses.json(...)`` keeps both.

## What is here

Bodies
    :func:`json` :func:`text` :func:`html` :func:`xml` :func:`raw` :func:`empty`

Status shorthands
    :func:`created` :func:`accepted` :func:`no_content`

Redirects
    :func:`redirect` :func:`permanent_redirect` :func:`see_other`
    :func:`temporary_redirect`

Files
    :func:`file` :func:`download`

Streaming
    :func:`stream` :func:`ndjson` :func:`sse`

Pagination
    :func:`paginate` :func:`apaginate`

Stopping early (these raise rather than return)
    :func:`abort` :func:`not_found`

The response classes themselves are re-exported too, for the rare handler that
wants to construct one directly or a subclass of its own.
"""

from __future__ import annotations

import typing
from typing import Any, AsyncIterable, AsyncIterator, Mapping

from sillo.core.http.response import (
    BaseResponse,
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from sillo.exceptions import HTTPException, NotFoundException
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

if typing.TYPE_CHECKING:
    from sillo.core.http.context import HttpContext


def _headers(headers: Mapping[str, str] | None) -> dict[str, str] | None:
    """Normalise a header mapping into the plain dict the classes take."""
    return dict(headers) if headers else None


# ── Bodies ────────────────────────────────────────────────────────────────


def json(
    data: Any,
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    indent: int | None = None,
    ensure_ascii: bool = True,
    use_encoder: bool = True,
    custom_encoder: Mapping[type, typing.Callable[[Any], Any]] | None = None,
) -> JSONResponse:
    """A JSON response. ``data`` is any JSON-encodable value or Pydantic model.

    Args:
        data: The payload to serialize.
        status_code: The HTTP status.
        headers: Extra headers.
        indent: Pretty-print with this indent. ``None`` sends it compact.
        ensure_ascii: Escape non-ASCII characters rather than sending UTF-8.
        use_encoder: Run the payload through ``jsonable_encoder`` first. Turn it
            off when the payload is already JSON-safe primitives, to avoid
            walking it a second time.
        custom_encoder: Per-type encoders, merged over the defaults.
    """
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers=_headers(headers),
        indent=indent,
        ensure_ascii=ensure_ascii,
        use_encoder=use_encoder,
        custom_encoder=dict(custom_encoder) if custom_encoder else None,
    )


def text(
    body: str = "",
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> PlainTextResponse:
    """A ``text/plain`` response."""
    return PlainTextResponse(
        body=body, status_code=status_code, headers=_headers(headers)
    )


def html(
    body: str = "",
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> HTMLResponse:
    """A ``text/html`` response."""
    return HTMLResponse(
        content=body, status_code=status_code, headers=_headers(headers)
    )


def xml(
    body: str = "",
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    content_type: str = "application/xml",
) -> BaseResponse:
    """An XML response.

    Args:
        body: The document, already serialized.
        status_code: The HTTP status.
        headers: Extra headers.
        content_type: Override for a more specific type, such as
            ``"application/atom+xml"`` or ``"image/svg+xml"``.
    """
    return BaseResponse(
        body=body,
        status_code=status_code,
        headers=_headers(headers),
        content_type=content_type,
    )


def raw(
    body: bytes | str = b"",
    *,
    content_type: str = "application/octet-stream",
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> BaseResponse:
    """A response whose body and content type you set yourself.

    The escape hatch for a media type with no helper of its own -- a protobuf
    payload, a generated image, ``text/csv``. Everything else here is this with
    the content type filled in.
    """
    return BaseResponse(
        body=body,
        status_code=status_code,
        headers=_headers(headers),
        content_type=content_type,
    )


def empty(
    status_code: int = 204,
    *,
    headers: Mapping[str, str] | None = None,
) -> BaseResponse:
    """A response with no body. Defaults to 204 No Content."""
    return BaseResponse(body=b"", status_code=status_code, headers=_headers(headers))


# ── Status shorthands ─────────────────────────────────────────────────────


def created(
    data: Any = None,
    *,
    location: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> BaseResponse:
    """201 Created, optionally pointing at the thing that was created.

    Args:
        data: The representation to return. ``None`` sends no body.
        location: The URL of the new resource, sent as ``Location``. RFC 9110
            expects this on a 201 whenever the resource has a URL of its own.
        headers: Extra headers.
    """
    merged = dict(headers or {})
    if location is not None:
        merged["location"] = location
    if data is None:
        return empty(201, headers=merged)
    return json(data, status_code=201, headers=merged)


def accepted(
    data: Any = None,
    *,
    headers: Mapping[str, str] | None = None,
) -> BaseResponse:
    """202 Accepted: the work was queued, not finished.

    What to answer when a handler hands the request to :mod:`sillo.work` rather
    than doing it inline. ``data`` typically carries a job id or a URL to poll.
    """
    if data is None:
        return empty(202, headers=headers)
    return json(data, status_code=202, headers=headers)


def no_content(*, headers: Mapping[str, str] | None = None) -> BaseResponse:
    """204 No Content. Spelled out, for when the status is the point."""
    return empty(204, headers=headers)


# ── Redirects ─────────────────────────────────────────────────────────────


def redirect(
    location: str,
    *,
    status_code: int = 302,
    headers: Mapping[str, str] | None = None,
) -> RedirectResponse:
    """A redirect to *location*.

    Defaults to 302 Found. Reach for one of the named helpers below when the
    distinction matters -- it decides whether the client repeats the method and
    body, and whether it caches the redirect forever.

    To redirect to a named route, resolve it first::

        return redirect(ctx.url_for("user_profile", user_id=42))
    """
    return RedirectResponse(
        url=location, status_code=status_code, headers=dict(headers or {})
    )


def permanent_redirect(
    location: str,
    *,
    preserve_method: bool = False,
    headers: Mapping[str, str] | None = None,
) -> RedirectResponse:
    """A permanent redirect, which clients are entitled to cache indefinitely.

    Sends 301 Moved Permanently. Clients have historically turned a redirected
    POST into a GET on a 301, which is usually what a moved page wants; pass
    ``preserve_method=True`` for 308, where the method and body are repeated
    as-is.

    Be deliberate: a wrongly-issued 301 is cached by browsers and is very hard
    to take back.
    """
    return redirect(
        location, status_code=308 if preserve_method else 301, headers=headers
    )


def see_other(
    location: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> RedirectResponse:
    """303 See Other: follow this with a GET, whatever the original method was.

    The right answer to a successful POST that should not be re-submitted when
    the visitor refreshes -- the post/redirect/get pattern.
    """
    return redirect(location, status_code=303, headers=headers)


def temporary_redirect(
    location: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> RedirectResponse:
    """307 Temporary Redirect: repeat the same method and body over there."""
    return redirect(location, status_code=307, headers=headers)


# ── Files ─────────────────────────────────────────────────────────────────


def file(
    path: str,
    filename: str | None = None,
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    content_disposition_type: str = "inline",
) -> FileResponse:
    """Serve a file from disk, with range-request support.

    The content type is guessed from the extension. Ranges, conditional
    requests and multipart range replies are handled for you, so a browser can
    seek within audio or video without downloading the whole thing.
    """
    return FileResponse(
        path=path,
        filename=filename,
        status_code=status_code,
        headers=_headers(headers),
        content_disposition_type=content_disposition_type,
    )


def download(
    path: str,
    filename: str | None = None,
    *,
    headers: Mapping[str, str] | None = None,
) -> FileResponse:
    """Serve a file as an attachment, so the browser saves rather than shows it."""
    return file(path, filename, headers=headers, content_disposition_type="attachment")


# ── Streaming ─────────────────────────────────────────────────────────────


def stream(
    content: AsyncIterator[str | bytes],
    *,
    status_code: int = 200,
    content_type: str = "text/plain",
    headers: Mapping[str, str] | None = None,
) -> StreamingResponse:
    """A streaming response from an async iterator of chunks.

    Nothing is buffered: each chunk is written as the iterator yields it, and
    no ``Content-Length`` is sent.
    """
    return StreamingResponse(
        content=content,
        status_code=status_code,
        content_type=content_type,
        headers=_headers(headers),
    )


def ndjson(
    source: AsyncIterable[Any],
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    encoder: typing.Callable[[Any], str] | None = None,
) -> StreamingResponse:
    """Newline-delimited JSON: one JSON document per line, streamed.

    For a result set too large to hold in memory or to make the client wait
    for. A consumer parses each line as it arrives rather than waiting for a
    closing bracket::

        @app.get("/export")
        async def export(ctx):
            async def rows():
                async for row in db.stream("SELECT * FROM events"):
                    yield row

            return ndjson(rows())

    Args:
        source: An async iterable of JSON-encodable objects, or of strings
            already encoded (sent as-is, one per line).
        status_code: The HTTP status.
        headers: Extra headers.
        encoder: Applied to non-string items. Defaults to the framework's
            ``jsonable_encoder`` followed by ``json.dumps``.
    """
    import json as _json

    from sillo.core.encoding import jsonable_encoder

    def _encode(item: Any) -> str:
        if encoder is not None:
            return encoder(item)
        return _json.dumps(jsonable_encoder(item), separators=(",", ":"))

    async def _lines() -> AsyncIterator[str]:
        async for item in source:
            line = item if isinstance(item, str) else _encode(item)
            yield line + "\n"

    return stream(
        _lines(),
        status_code=status_code,
        content_type="application/x-ndjson",
        headers=headers,
    )


def sse(
    source: AsyncIterable[Any],
    *,
    keepalive: float | None = 15.0,
    ping: str = "ping",
    retry: int | None = None,
    encoder: typing.Callable[[Any], str] | None = None,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> StreamingResponse:
    """A Server-Sent Events stream.

    Yield a ``dict`` (JSON-encoded), a ``str`` (sent as-is), or a
    :class:`~sillo.http.sse.ServerSentEvent` for control over the event name, id
    and reconnection delay::

        @app.get("/events")
        async def events(ctx):
            async def source():
                while True:
                    yield {"price": await next_tick()}

            return sse(source())

    Args:
        source: An async iterable of events.
        keepalive: Seconds of silence after which a comment line is sent to stop
            an idle connection being closed by a proxy. ``None`` disables it.
            The default is below the 60s that nginx and most load balancers use
            for ``proxy_read_timeout``.
        ping: Comment text used for the keepalive.
        retry: Reconnection delay in milliseconds, sent once at the start.
            ``EventSource`` remembers it across reconnects.
        encoder: Applied to non-string payloads. Defaults to ``json.dumps``.
        status_code: Response status.
        headers: Extra headers, merged over the defaults below.

    Returns:
        The streaming response to return from the handler.

    Note:
        Three headers are set that a plain :func:`stream` would not.
        ``no-cache`` keeps the response out of caches; ``no-transform`` stops a
        proxy re-encoding it; and ``x-accel-buffering: no`` disables nginx's
        response buffering, without which events are held back and delivered in
        batches rather than as they happen. Pass them in *headers* to override
        any of it.
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

    return stream(
        sse_stream(source, **options),
        content_type="text/event-stream",
        status_code=status_code,
        headers=merged,
    )


# ── Pagination ────────────────────────────────────────────────────────────


#: Keys understood by the built-in pagination strategies. Anything else in
#: ``**kwargs`` is treated as a per-request parameter override.
_PAGINATION_CONFIG_KEYS = frozenset(
    {
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
)


def _resolve_strategy(
    strategy: str | BasePaginationStrategy, kwargs: dict[str, Any]
) -> BasePaginationStrategy:
    """Turn a strategy name into a configured strategy instance."""
    if not isinstance(strategy, str):
        return strategy

    strategy_kwargs = {k: v for k, v in kwargs.items() if k in _PAGINATION_CONFIG_KEYS}
    if strategy == "page_number":
        return PageNumberPagination(**strategy_kwargs)
    if strategy == "limit_offset":
        return LimitOffsetPagination(**strategy_kwargs)
    if strategy == "cursor":
        return CursorPagination(**strategy_kwargs)
    raise ValueError(f"Unknown pagination strategy: {strategy}")


def paginate(
    ctx: HttpContext,
    objects: list[Any],
    strategy: str | BasePaginationStrategy = "page_number",
    data_handler: type[SyncListDataHandler] = SyncListDataHandler,
    **kwargs: Any,
) -> JSONResponse:
    """Paginate *objects* and return the page as JSON.

    The context is the first argument because the page is cut from the incoming
    query string, and the next/previous links are built from the request URL::

        @app.get("/articles")
        async def index(ctx):
            return paginate(ctx, await Article.all(), max_page_size=50)

    Args:
        ctx: The context, read for the request URL and query parameters.
        objects: The items to paginate.
        strategy: ``"page_number"``, ``"limit_offset"``, ``"cursor"``, or a
            strategy instance.
        data_handler: How to read the collection. Defaults to a plain list.
        **kwargs: Strategy configuration, or per-request parameter overrides.
    """
    paginator = SyncPaginator(
        data_handler=data_handler(objects),
        pagination_strategy=_resolve_strategy(strategy, kwargs),
        base_url=str(ctx.url),
        request_params=dict(ctx.query_params),
    )
    return json(paginator.paginate(**kwargs))


async def apaginate(
    ctx: HttpContext,
    objects: list[Any],
    strategy: str | BasePaginationStrategy = "page_number",
    data_handler: type[AsyncListDataHandler] = AsyncListDataHandler,
    **kwargs: Any,
) -> JSONResponse:
    """Paginate *objects* asynchronously and return the page as JSON.

    The async twin of :func:`paginate`, for data handlers that read their
    collection with ``await`` -- a queryset that counts and slices in the
    database rather than in memory.
    """
    paginator = AsyncPaginator(
        data_handler=data_handler(objects),
        pagination_strategy=_resolve_strategy(strategy, kwargs),
        base_url=str(ctx.url),
        request_params=dict(ctx.query_params),
    )
    return json(await paginator.paginate(**kwargs))


# ── Stopping early ────────────────────────────────────────────────────────


def abort(
    status_code: int,
    detail: Any | None = None,
    headers: Mapping[str, str] | None = None,
) -> typing.NoReturn:
    """Stop the request by raising an :class:`HTTPException`.

    Unlike the builders above, ``abort`` does not return a response. It raises
    immediately, so the exception middleware renders a consistent error envelope
    and nothing after the call runs.

    Args:
        status_code: HTTP status code for the error (e.g. 400, 401, 403).
        detail: Optional error detail / message. Rendered by the handler.
        headers: Optional headers attached to the raised exception.

    Raises:
        HTTPException: Always, with the given status code and detail.

    Examples:
        ```python
        @app.get("/admin")
        async def admin(ctx):
            if not ctx.user.is_admin:
                abort(403, detail="Admins only")
            return json({"ok": True})
        ```
    """
    raise HTTPException(
        status_code=status_code, detail=detail, headers=dict(headers or {})
    )


def not_found(
    detail: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> typing.NoReturn:
    """Stop the request with a 404 by raising a :class:`NotFoundException`.

    Shorthand for ``abort(404, detail=...)``. The framework renders it through
    the registered 404 handler, which negotiates JSON, HTML or plain text.

    Args:
        detail: Optional message describing what was not found.
        headers: Optional headers attached to the raised exception.

    Raises:
        NotFoundException: Always, with status code 404.

    Examples:
        ```python
        @app.get("/items/{item_id}")
        async def get_item(ctx, item_id: int):
            item = await db.get(item_id)
            if item is None:
                not_found(detail=f"Item {item_id} not found")
            return json(item)
        ```
    """
    raise NotFoundException(detail=detail, headers=dict(headers or {}))


# Grouped by what each one is for rather than alphabetically: this list is
# the module's table of contents, and sorting it would scatter the four
# redirects and the three streaming helpers through the whole thing.
__all__ = [  # noqa: RUF022
    # Response classes, for constructing one directly or subclassing.
    "BaseResponse",
    "FileResponse",
    "HTMLResponse",
    "JSONResponse",
    "PlainTextResponse",
    "RedirectResponse",
    "StreamingResponse",
    # Bodies
    "json",
    "text",
    "html",
    "xml",
    "raw",
    "empty",
    # Status shorthands
    "created",
    "accepted",
    "no_content",
    # Redirects
    "redirect",
    "permanent_redirect",
    "see_other",
    "temporary_redirect",
    # Files
    "file",
    "download",
    # Streaming
    "stream",
    "ndjson",
    "sse",
    # Pagination
    "paginate",
    "apaginate",
    # Stopping early
    "abort",
    "not_found",
]
