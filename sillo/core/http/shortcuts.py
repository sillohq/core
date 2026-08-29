"""Free functions that build a response.

Sillo v1 has no request-scoped response manager. A handler builds its reply by
calling one of these and returning it; middleware ends the chain early the same
way. Each returns a plain :class:`~sillo.core.http.response.BaseResponse`
subclass, so the object that comes back is the response -- there is no wrapper
to unwrap and nothing to mutate through.

    from sillo import json, redirect

    def show(ctx, id: int):
        return json({"id": id})

    async def gate(ctx, call_next):
        if ctx.user is None:
            return redirect("/login")      # break the chain
        return await call_next()

Everything the response itself owns -- status, headers, cookies, caching --
lives on what comes back::

    return json(payload, status_code=201).set_cookie("seen", "1")
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
        headers=dict(headers) if headers else None,
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
        body=body,
        status_code=status_code,
        headers=dict(headers) if headers else None,
    )


def html(
    body: str = "",
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> HTMLResponse:
    """A ``text/html`` response."""
    return HTMLResponse(
        content=body,
        status_code=status_code,
        headers=dict(headers) if headers else None,
    )


def empty(
    status_code: int = 204,
    *,
    headers: Mapping[str, str] | None = None,
) -> BaseResponse:
    """A response with no body."""
    return BaseResponse(
        body=b"",
        status_code=status_code,
        headers=dict(headers) if headers else None,
    )


def redirect(
    location: str,
    *,
    status_code: int = 302,
    headers: Mapping[str, str] | None = None,
) -> RedirectResponse:
    """A redirect to *location*."""
    return RedirectResponse(
        url=location,
        status_code=status_code,
        headers=dict(headers) if headers else {},
    )


def file(
    path: str,
    filename: str | None = None,
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    content_disposition_type: str = "inline",
) -> FileResponse:
    """Serve a file from disk, with range-request support."""
    return FileResponse(
        path=path,
        filename=filename,
        status_code=status_code,
        headers=dict(headers) if headers else None,
        content_disposition_type=content_disposition_type,
    )


def download(
    path: str,
    filename: str | None = None,
    *,
    headers: Mapping[str, str] | None = None,
) -> FileResponse:
    """Serve a file as an attachment, so the browser saves rather than shows it."""
    return file(
        path,
        filename,
        headers=headers,
        content_disposition_type="attachment",
    )


def stream(
    content: AsyncIterator[str | bytes],
    *,
    status_code: int = 200,
    content_type: str = "text/plain",
    headers: Mapping[str, str] | None = None,
) -> StreamingResponse:
    """A streaming response from an async iterator of chunks."""
    return StreamingResponse(
        content=content,
        status_code=status_code,
        content_type=content_type,
        headers=dict(headers) if headers else None,
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


def abort(
    status_code: int,
    detail: Any | None = None,
    headers: Mapping[str, str] | None = None,
) -> typing.NoReturn:
    """Stop the request by raising an :class:`HTTPException`.

    Unlike the builders above, ``abort`` does not return a response. It raises
    immediately so the exception middleware renders a consistent error envelope.

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
    collection with ``await``.
    """
    paginator = AsyncPaginator(
        data_handler=data_handler(objects),
        pagination_strategy=_resolve_strategy(strategy, kwargs),
        base_url=str(ctx.url),
        request_params=dict(ctx.query_params),
    )
    return json(await paginator.paginate(**kwargs))


__all__ = [
    "abort",
    "apaginate",
    "download",
    "empty",
    "file",
    "html",
    "json",
    "not_found",
    "paginate",
    "redirect",
    "sse",
    "stream",
    "text",
]
