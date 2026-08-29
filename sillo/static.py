import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sillo.core.http import HttpContext
from sillo.core.routing import BaseRouter
from sillo.responses import file as file_response
from sillo.responses import json
from sillo.types import Receive, Scope, Send


class StaticFiles(BaseRouter):
    """
    ASGI application for serving static files from one or more directories.

    Provides secure static file serving with support for multiple source
    directories, file extension allow-listing, custom 404 handlers, and
    cache control headers. Inherits from ``BaseRouter`` to integrate with
    the sillo routing system. Path traversal attacks are prevented by
    validating that resolved file paths remain within the configured
    directory roots.

    Attributes:
        directories: A list of resolved ``Path`` objects representing the
            directories from which files are served.
        allowed_extensions: A set of file extensions (without dots) that
            are permitted to be served. An empty set means all extensions
            are allowed.
        custom_404_handler: An optional async callable invoked when a
            requested file is not found in any configured directory.
        cache_control: An optional ``Cache-Control`` header value to set
            on all served file responses.
    """

    def __init__(
        self,
        directory: str | Path | None = None,
        directories: list[str | Path] | None = None,
        allowed_extensions: list[str] | None = None,
        custom_404_handler: Callable[[HttpContext], Any] | None = None,
        cache_control: str | None = None,
    ):
        """
        Initialize the StaticFiles application with directory and serving config.

        Args:
            directory: A single directory path (string or ``Path``) from which
                to serve static files. If ``directories`` is also provided,
                this is ignored in favor of the list.
            directories: A list of directory paths to serve files from. Files
                are searched in order; the first matching file is returned.
                If neither this nor ``directory`` is provided, no files are
                served.
            allowed_extensions: An optional list of file extensions (e.g.,
                ``["html", "css", "js"]``) that are allowed to be served.
                Extensions are normalized by stripping leading dots and
                lowercasing. If ``None`` or empty, all extensions are allowed.
            custom_404_handler: An optional async callable that receives
                ``(request, response)`` and returns a response when a
                requested file is not found. If ``None``, a default JSON
                404 response is returned.
            cache_control: An optional ``Cache-Control`` header value to
                apply to all served file responses (e.g.,
                ``"public, max-age=3600"``).

        Returns:
            None. Initializes the static file serving application.

        Example::

            static = StaticFiles(
                directory="./public",
                allowed_extensions=["html", "css", "js", "png"],
                cache_control="public, max-age=86400",
            )
        """
        if not directories:
            directories = [directory] if directory else []
        self.directories = [self._ensure_directory(d) for d in directories or []]
        self.allowed_extensions = {
            ext.lower().lstrip(".") for ext in (allowed_extensions or [])
        }
        self.custom_404_handler = custom_404_handler
        self.cache_control = cache_control

    def _ensure_directory(self, path: str | Path) -> Path:
        """
        Validate and resolve a directory path, creating it if it does not exist.

        Resolves the given path to an absolute path, creates the directory
        (and any missing parents) if it does not already exist, and verifies
        that the resolved path is actually a directory.

        Args:
            path: The directory path to validate, as a string or ``Path``
                object. Relative paths are resolved against the current
                working directory.

        Returns:
            The resolved absolute ``Path`` object pointing to the validated
            directory.

        Raises:
            ValueError: If the resolved path exists but is not a directory
                (e.g., it is a regular file or a symlink to a file).
        """
        """Ensure directory exists and return resolved Path"""
        directory = Path(path).resolve()
        if not directory.exists():
            os.makedirs(directory, exist_ok=True)
        if not directory.is_dir():
            raise ValueError(f"{directory} is not a directory")
        return directory

    def _is_safe_path(self, path: Path, root: Path) -> bool:
        """
        Check whether a resolved file path is safely contained within a root directory.

        Prevents path traversal attacks by verifying that the fully resolved
        absolute path of the requested file is a descendant of the configured
        root directory. Uses ``Path.is_relative_to`` for the containment check.

        Args:
            path: The resolved file path to validate. Should already be
                resolved to an absolute path before calling this method.
            root: The root directory path that the file must be contained
                within. Must also be an absolute resolved path.

        Returns:
            ``True`` if the file path is safely within the root directory,
            ``False`` otherwise (including when resolution fails due to
            ``ValueError`` or ``RuntimeError``).
        """
        """Check if the path is safe to serve"""
        try:
            full_path = path.resolve()
            return full_path.is_relative_to(root)
        except (ValueError, RuntimeError):
            return False

    def _is_extension_allowed(self, file_path: Path) -> bool:
        """
        Check whether a file's extension is in the allowed extensions set.

        Compares the file's suffix (extension) against the configured
        ``allowed_extensions`` set. If no extensions were configured
        (empty set), all extensions are permitted by default.

        Args:
            file_path: The ``Path`` object of the file to check. The
                file's suffix (e.g., ``".html"``) is extracted,
                lowercased, and stripped of its leading dot before
                comparison.

        Returns:
            ``True`` if the file extension is allowed (or if no extension
            filter is configured), ``False`` if the extension is not in
            the allowed set.
        """
        """Check if the file extension is in the allowed list"""
        if not self.allowed_extensions:
            return True
        return file_path.suffix.lower().lstrip(".") in self.allowed_extensions

    async def _handle(self, request: HttpContext):
        """
        Handle an incoming static file request by locating and serving the file.

        Searches through the configured directories in order for a file matching
        the request path. Validates that the request method is GET, the file path
        is safe (no traversal), the file exists, and the extension is allowed.
        If a match is found, the file is served with inline content disposition
        and optional cache control headers. Falls back to the custom 404 handler
        or a default JSON 404 response if no file is found.

        Args:
            request: The context for the request. The path is extracted from
                ``request.scope["path"]`` and the method is checked to ensure
                only GET requests are served.

        Returns:
            A response containing either the served file with
            appropriate headers, a 405 error for non-GET methods, a 404
            error from the custom handler, or a default JSON 404 response.
        """
        path = request.scope.get("path", "").lstrip("/")
        if request.method != "GET":
            return json("Method not allowed", status_code=405)
        for directory in self.directories:
            try:
                file_path = (directory / path).resolve()
                if (
                    self._is_safe_path(file_path, directory)
                    and file_path.is_file()
                    and self._is_extension_allowed(file_path)
                ):
                    response = file_response(
                        str(file_path), content_disposition_type="inline"
                    )
                    if self.cache_control:
                        response.set_header("cache-control", self.cache_control)
                    return response
            except (ValueError, RuntimeError):
                continue

        # Use custom 404 handler if provided, otherwise use default
        if self.custom_404_handler:
            return self.custom_404_handler(request)
        return json("Resource not found", status_code=404)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """
        ASGI application entry point for serving static file requests.

        Creates the ``HttpContext`` from the raw ASGI scope, delegates to
        ``_handle`` for file resolution and serving, then sends the resulting
        response through the ASGI send channel.

        Args:
            scope: The ASGI connection scope dictionary containing request
                metadata such as type, path, headers, and query string.
            receive: The ASGI receive callable for consuming the request
                body messages from the server.
            send: The ASGI send callable for transmitting the response
                messages back to the server and ultimately the client.

        Returns:
            None. The response is sent asynchronously through the ``send``
            callable as per the ASGI specification.
        """
        request = HttpContext(scope, receive)
        response = await self._handle(request)
        if response is not None:
            await response(scope, receive, send)
