from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from nexios.http import Request, Response
from nexios.routing.base import BaseRouter
from nexios.types import Receive, Scope, Send

FallbackType = Optional[Union[str, bool]]


class FrontendApp(BaseRouter):
    """ASGI application that serves a frontend SPA build directory with fallback routing.

    Designed for single-page applications (SPAs). Serves static files from the
    build output directory, and when a file is not found, falls back to a
    configurable HTML file (typically ``index.html``) so that client-side
    routing works correctly.

    The ``fallback`` parameter accepts:

    * ``"auto"`` (default) — tries ``404.html`` first, then ``index.html``.
    * An explicit filename relative to *directory* (e.g. ``"app.html"``).
    * ``None`` or ``False`` — no fallback; returns 404 when a file is missing.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        fallback: FallbackType = "auto",
        cache_control: Optional[str] = None,
    ) -> None:
        self.directory = Path(directory).resolve()
        if not self.directory.exists():
            os.makedirs(self.directory, exist_ok=True)
        if not self.directory.is_dir():
            raise ValueError(f"{directory} is not a directory")
        self.fallback = fallback
        self.cache_control = cache_control

    def _resolve_fallback_path(self) -> Optional[Path]:
        if self.fallback in (None, False):
            return None
        if self.fallback == "auto":
            for candidate in ("404.html", "index.html"):
                p = self.directory / candidate
                if p.is_file():
                    return p
            return None
        p = self.directory / str(self.fallback)
        return p if p.is_file() else None

    def _is_safe_path(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
            return resolved.is_relative_to(self.directory)
        except (ValueError, RuntimeError):
            return False

    async def __call__(  # type: ignore[override]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        request = Request(scope, receive)
        response = Response(request)

        if request.method != "GET":
            handler_result = response.json("Method not allowed", status_code=405)
        else:
            handler_result = await self._handle(request, response)

        if handler_result is not None:
            if hasattr(handler_result, "get_response"):
                final = handler_result.get_response()
                await final(scope, receive, send)
            else:
                await handler_result(scope, receive, send)
        else:
            result = response.get_response()
            if result is not None:
                response = result  # type: ignore[assignment]
            await response(scope, receive, send)

    async def _handle(self, request: Request, response: Response) -> Optional[Response]:
        raw_path: str = request.scope.get("path", "")
        relative_path: str = raw_path.lstrip("/")

        file_candidate = self.directory / relative_path
        if self._is_safe_path(file_candidate) and file_candidate.is_file():
            response.file(str(file_candidate), content_disposition_type="inline")
            if self.cache_control:
                response.set_header("cache-control", self.cache_control)
            return response

        fallback_path = self._resolve_fallback_path()
        if fallback_path is not None:
            response.file(str(fallback_path), content_disposition_type="inline")
            if self.cache_control:
                response.set_header("cache-control", self.cache_control)
            return response

        return response.json("Resource not found", status_code=404)
