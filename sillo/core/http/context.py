"""The v1 request/connection context objects.

Sillo v1 passes a single ``ctx`` object to every handler and every middleware in
place of the old ``(request, response)`` pair. The hierarchy is:

    BaseContext            -- the shared ASGI-connection surface
      HttpContext          -- an HTTP request; the argument to HTTP handlers
      WebSocketContext     -- a WebSocket connection; the argument to WS handlers

There is no ``Request`` and no request-scoped ``Response`` manager in v1. A
handler returns a response object built by the free helpers in
``sillo.core.http.shortcuts`` (``json``, ``html`` ...), and middleware ends the
chain early by returning one of those instead of calling ``call_next``.
"""

from __future__ import annotations

from functools import cached_property
from typing import Any

from sillo.core.http.request import HTTPConnection as _Connection
from sillo.core.http.request import Request as _HttpBase
from sillo.websockets.base import WebSocket as _SocketBase


class _MergedParams:
    """Adds ``ctx.params`` -- path parameters merged over query parameters.

    Path values win on a key collision; both are still reachable unmerged via
    ``ctx.path_params`` and ``ctx.query_params``.
    """

    path_params: dict[str, Any]

    @cached_property
    def params(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        query = getattr(self, "query_params", None)
        if query is not None:
            for key in query:
                merged[key] = query[key]
        merged.update(self.path_params)
        return merged


class BaseContext(_MergedParams, _Connection):
    """The connection surface shared by :class:`HttpContext` and
    :class:`WebSocketContext`: ``scope``, ``headers``, ``cookies``,
    ``path_params``, ``query_params``, ``params``, ``state``, ``user``,
    ``client``, ``app`` and ``url_for``.
    """


class HttpContext(_MergedParams, _HttpBase):
    """The single argument passed to every HTTP handler and middleware.

    Everything the old ``Request`` carried lives here (``method``, ``await
    ctx.json``, ``await ctx.body``, ``await ctx.form``, ``ctx.files``,
    ``ctx.validated_data`` ...), plus ``ctx.params``.
    """


class WebSocketContext(_MergedParams, _SocketBase):
    """The single argument passed to every WebSocket handler.

    Carries the WebSocket state machine (``accept``, ``receive``, ``send``,
    ``send_json``, ``receive_json``, ``close``, ``iter_*``) alongside the shared
    ``BaseContext`` surface and ``ctx.params``.
    """


__all__ = ["BaseContext", "HttpContext", "WebSocketContext"]
