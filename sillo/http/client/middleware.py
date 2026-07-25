from __future__ import annotations

import abc
import typing

if typing.TYPE_CHECKING:
    from typing import Any, AsyncGenerator, Callable, Optional

    from httpx import Request, Response

    AsyncSend = Callable[[Request], AsyncGenerator[Response, None]]
    NextCall = Callable[[Request], AsyncGenerator[Response, None]]


class HTTPMiddleware(abc.ABC):
    """Abstract base class for HTTP client middleware.

    Middleware wraps the outgoing request and incoming response,
    allowing cross-cutting concerns like logging, authentication,
    header injection, and response transformation.
    """

    @abc.abstractmethod
    async def handle(
        self,
        request: Request,
        next_call: NextCall,
    ) -> AsyncGenerator[Response, None]: ...


class MiddlewareChain:
    """Orchestrates an ordered sequence of middleware around a final send call."""

    def __init__(self, middlewares: list[HTTPMiddleware]) -> None:
        self._middlewares = middlewares

    async def run(
        self,
        request: Request,
        final_send: AsyncSend,
    ) -> AsyncGenerator[Response, None]:
        async def _build_chain(index: int) -> NextCall:
            if index >= len(self._middlewares):
                return final_send

            middleware = self._middlewares[index]
            next_middleware = await _build_chain(index + 1)

            async def _chain(req: Request) -> AsyncGenerator[Response, None]:
                async for response in middleware.handle(req, next_middleware):  # ty: ignore[not-iterable]
                    yield response

            return _chain

        entry_point = await _build_chain(0)
        async for response in entry_point(request):
            yield response


class LoggingMiddleware(HTTPMiddleware):
    """Middleware that logs request and response details."""

    def __init__(self, logger: Optional[Any] = None) -> None:
        import logging

        self._logger = logger or logging.getLogger("sillo.http")

    async def handle(  # ty: ignore[invalid-method-override]
        self,
        request: Request,
        next_call: NextCall,
    ) -> AsyncGenerator[Response, None]:
        import time

        start = time.monotonic()
        async for response in next_call(request):
            duration = time.monotonic() - start
            self._logger.info(
                "%s %s -> %d (%.3fs)",
                request.method,
                request.url,
                response.status_code,
                duration,
            )
            yield response


class HeaderInjectionMiddleware(HTTPMiddleware):
    """Middleware that injects headers into every outgoing request."""

    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = headers

    async def handle(  # ty: ignore[invalid-method-override]
        self,
        request: Request,
        next_call: NextCall,
    ) -> AsyncGenerator[Response, None]:
        for name, value in self._headers.items():
            request.headers[name] = value
        async for response in next_call(request):
            yield response


class BaseURLMiddleware(HTTPMiddleware):
    """Middleware that prepends a base URL to relative request URLs."""

    def __init__(self, base_url: str) -> None:
        from httpx import URL

        self._base_url = URL(base_url)

    async def handle(  # ty: ignore[invalid-method-override]
        self,
        request: Request,
        next_call: NextCall,
    ) -> AsyncGenerator[Response, None]:
        if not request.url.path.startswith(self._base_url.path):
            request.url = request.url.copy_with(
                scheme=self._base_url.scheme or request.url.scheme,
                host=self._base_url.host or request.url.host,
                port=self._base_url.port or request.url.port,
            )
        async for response in next_call(request):
            yield response


__all__ = [
    "HTTPMiddleware",
    "MiddlewareChain",
    "LoggingMiddleware",
    "HeaderInjectionMiddleware",
    "BaseURLMiddleware",
]
