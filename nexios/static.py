import os
from pathlib import Path
from typing import Any, Callable, List, Optional, Union

from nexios.http import Request, Response
from nexios.routing import BaseRouter
from nexios.types import Receive, Scope, Send


class StaticFiles(BaseRouter):
    def __init__(
        self,
        directory: Optional[Union[str, Path]] = None,
        directories: Optional[List[Union[str, Path]]] = None,
        allowed_extensions: Optional[List[str]] = None,
        custom_404_handler: Optional[Callable[[Request, Response], Any]] = None,
        cache_control: Optional[str] = None,
    ):
        if not directories:
            directories = [directory] if directory else []
        self.directories = [self._ensure_directory(d) for d in directories or []]
        self.allowed_extensions = set(
            ext.lower().lstrip(".") for ext in (allowed_extensions or [])
        )
        self.custom_404_handler = custom_404_handler
        self.cache_control = cache_control

    def _ensure_directory(self, path: Union[str, Path]) -> Path:
        """Ensure directory exists and return resolved Path"""
        directory = Path(path).resolve()
        if not directory.exists():
            os.makedirs(directory, exist_ok=True)
        if not directory.is_dir():
            raise ValueError(f"{directory} is not a directory")
        return directory

    def _is_safe_path(self, path: Path) -> bool:
        """Check if the path is safe to serve"""
        try:
            full_path = path.resolve()
            return any(
                str(full_path).startswith(str(directory))
                for directory in self.directories
            )
        except (ValueError, RuntimeError):
            return False

    def _is_extension_allowed(self, file_path: Path) -> bool:
        """Check if the file extension is in the allowed list"""
        if not self.allowed_extensions:
            return True
        return file_path.suffix.lower().lstrip(".") in self.allowed_extensions

    async def _handle(self, request: Request, response: Response):
        path = request.scope.get("path", "").lstrip("/")
        if request.method != "GET":
            return response.json("Method not allowed", status_code=405)
        for directory in self.directories:
            try:
                file_path = (directory / path).resolve()
                if (
                    self._is_safe_path(file_path)
                    and file_path.is_file()
                    and self._is_extension_allowed(file_path)
                ):
                    

                    response.file(
                        str(file_path), content_disposition_type="inline"
                    )
                    if self.cache_control:
                        response.set_header("cache-control", self.cache_control)
                    return response
            except (ValueError, RuntimeError):
                continue

        # Use custom 404 handler if provided, otherwise use default
        if self.custom_404_handler:
            return self.custom_404_handler(request, response)
        else:
            return response.json("Resource not found", status_code=404)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        request = Request(scope, receive)
        response = Response(request)

        # Call the handler and get the result
        handler_result = await self._handle(request, response)

        # If handler returned a custom response, use it directly
        if handler_result is not None:
            if hasattr(handler_result, "get_response"):
                # It's a NexiosResponse, get the BaseResponse
                final_response = handler_result.get_response()
                await final_response(scope, receive, send)
            else:
                # It's already a BaseResponse
                await handler_result(scope, receive, send)
        else:
            # Use the original response flow
            result = response.get_response()
            if result is not None:
                response = result
            await response(scope, receive, send)
