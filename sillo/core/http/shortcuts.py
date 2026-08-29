"""Free functions that build a response.

Sillo v1 has no request-scoped ``Response`` manager. A handler builds its reply
by calling one of these and returning it; middleware ends the chain early the
same way. Each returns a plain :class:`~sillo.core.http.response.BaseResponse`
subclass -- there is no dependency on the fluent ``Responder``.

    from sillo import json, redirect

    def show(ctx):
        return json({"id": ctx.params["id"]})

    async def gate(ctx, call_next):
        if not ctx.user:
            return redirect("/login")          # break the chain
        return await call_next()
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping

from sillo.core.http.response import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)


def json(
    data: Any,
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """A JSON response. ``data`` is any JSON-encodable value or Pydantic model."""
    return JSONResponse(
        content=data, status_code=status_code, headers=dict(headers) if headers else None
    )


def text(
    body: str = "",
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> PlainTextResponse:
    """A ``text/plain`` response."""
    return PlainTextResponse(
        body=body, status_code=status_code, headers=dict(headers) if headers else None
    )


def html(
    body: str = "",
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> HTMLResponse:
    """A ``text/html`` response."""
    return HTMLResponse(
        content=body, status_code=status_code, headers=dict(headers) if headers else None
    )


def redirect(
    location: str,
    *,
    status_code: int = 307,
    headers: Mapping[str, str] | None = None,
) -> RedirectResponse:
    """A redirect. Defaults to 307 so the method and body are preserved."""
    return RedirectResponse(
        url=location, status_code=status_code, headers=dict(headers) if headers else {}
    )


def file(
    path: str,
    *,
    filename: str | None = None,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    content_disposition_type: str = "inline",
) -> FileResponse:
    """Stream a file from disk, with range-request support."""
    return FileResponse(
        path=path,
        filename=filename,
        status_code=status_code,
        headers=dict(headers) if headers else None,
        content_disposition_type=content_disposition_type,
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


__all__ = ["json", "text", "html", "redirect", "file", "stream"]
