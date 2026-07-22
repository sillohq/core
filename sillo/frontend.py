from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from sillo.http import Request, Response
from sillo.routing.base import BaseRouter
from sillo.types import Receive, Scope, Send

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

    Attributes:
        directory: The resolved absolute path to the static files directory.
        fallback: The fallback strategy for unresolved routes. Can be
            ``"auto"``, a filename string, ``None``, or ``False``.
        cache_control: An optional ``Cache-Control`` header value to set
            on all served responses.

    Args:
        directory: Path to the directory containing the frontend build
            output. Will be created if it does not exist.
        fallback: Fallback strategy for unresolved routes. Defaults to
            ``"auto"`` which tries ``404.html`` then ``index.html``.
        cache_control: Optional ``Cache-Control`` header value to include
            on every response served by this application.

    Raises:
        ValueError: If the resolved directory path points to an existing
            file rather than a directory.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        fallback: FallbackType = "auto",
        cache_control: Optional[str] = None,
    ) -> None:
        """Initialize the frontend application with directory and fallback config.

        Resolves the given directory path to an absolute path and creates it
        if it does not already exist. Validates that the path is a directory
        and stores the fallback and cache control configuration for use
        during request handling.

        Args:
            directory: Path to the directory containing the frontend build
                output. Will be created if it does not exist.
            fallback: Fallback strategy for unresolved routes. Defaults to
                ``"auto"`` which tries ``404.html`` then ``index.html``.
            cache_control: Optional ``Cache-Control`` header value to include
                on every response served by this application.

        Raises:
            ValueError: If the resolved directory path points to an existing
                file rather than a directory.
        """
        self.directory = Path(directory).resolve()
        if not self.directory.exists():
            os.makedirs(self.directory, exist_ok=True)
        if not self.directory.is_dir():
            raise ValueError(f"{directory} is not a directory")
        self.fallback = fallback
        self.cache_control = cache_control

    def _resolve_fallback_path(self) -> Optional[Path]:
        """Resolve the fallback HTML file path based on the configured strategy.

        Determines which file to serve when the requested path does not match
        any static file in the directory. Supports three modes: automatic
        detection (tries ``404.html`` then ``index.html``), explicit filename
        relative to the directory, or disabled (returns ``None``).

        Returns:
            The resolved ``Path`` to the fallback file if it exists and is
            a regular file, or ``None`` if fallback is disabled or no
            candidate file exists on disk.
        """
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
        """Check whether a path is safely contained within the served directory.

        Resolves the given path to its absolute form and verifies that it
        is a descendant of the configured serving directory. This prevents
        directory traversal attacks where a malicious request path could
        escape the intended file serving root via ``..`` segments or
        symbolic links.

        Args:
            path: The file path to validate against the serving directory.
                Should be constructed from user-supplied request paths.

        Returns:
            ``True`` if the resolved path is within the serving directory,
            ``False`` if it escapes the directory or if resolution fails
            due to a ``ValueError`` or ``RuntimeError``.
        """
        try:
            resolved = path.resolve()
            return resolved.is_relative_to(self.directory)
        except (ValueError, RuntimeError):
            return False

    async def __call__(  # type: ignore[override]
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Handle an incoming ASGI request as the frontend serving application.

        Constructs a ``Request`` and ``Response`` from the ASGI scope, then
        dispatches to the appropriate handler based on the HTTP method. Only
        ``GET`` requests are served; all other methods receive a 405 response.
        For ``GET`` requests, delegates to ``_handle`` to resolve the file
        or fallback, then sends the resulting response through the ASGI
        send channel.

        Args:
            scope: The ASGI connection scope dictionary containing metadata
                about the incoming request (method, path, headers, etc.).
            receive: An async callable that yields ASGI message dictionaries
                from the client. Used for reading the request body.
            send: An async callable that accepts ASGI message dictionaries
                to send back to the client. Used for writing the response.

        Returns:
            None. The response is sent directly through the ASGI ``send``
            channel.
        """
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
        """Resolve and serve the requested file or fallback for a GET request.

        Strips the leading slash from the request path and attempts to locate
        a matching file within the serving directory. If a file is found and
        the path is safe, it is served inline with optional cache control
        headers. If no file matches, the fallback path is resolved and served
        instead. If neither a file nor a fallback is available, a 404 JSON
        response is returned.

        Args:
            request: The incoming HTTP request object containing the path
                and other request metadata.
            response: The response object used to construct and return the
                appropriate file or JSON response.

        Returns:
            A ``Response`` object configured to serve the matched file,
            the fallback file, or a 404 error. Never returns ``None``
            in practice, but typed as ``Optional`` for interface compatibility.
        """
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
