"""
Template context middleware for Nexios.
"""

from typing import Any, Awaitable, Callable, Dict, Optional

from nexios.middleware import BaseMiddleware
from nexios.types import Request, Response
from nexios.utils.async_helpers import is_async_callable


class TemplateContextMiddleware(BaseMiddleware):
    """Middleware for injecting template context."""

    def __init__(
        self,
        default_context: Dict[str, Any] | None = None,
        context_processor: Callable[[Request], Awaitable[Dict[str, Any]]] | None = None,
    ):
        """Initialize middleware with context."""
        self.default_context = default_context or {}
        self.context_processor = context_processor

    async def __call__(
        self,
        request: Request,
        response: Response,
        call_next: Callable[..., Awaitable[Any]],
    ) -> Response:
        """Process request and inject context."""
        context = self.default_context.copy()

        if self.context_processor:
            if not is_async_callable(self.context_processor):
                request_context = self.context_processor(request)
            else:
                request_context = await self.context_processor(request)
            context.update(request_context)  # ty :ignore[no-matching-overload]

        context.update(
            {
                "request": request,
                "url_for": request.base_app.url_for,
                "csrf_token": request.state.csrf_token,
            }
        )

        request.state.template_context = context
        return await call_next()


def template_context(
    default_context: Optional[Dict[str, Any]] = None,
    context_processor: Optional[Callable[[Request], Awaitable[Dict[str, Any]]]] = None,
):
    """Create template context middleware."""
    return TemplateContextMiddleware(default_context, context_processor)
