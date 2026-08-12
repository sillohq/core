"""
Template context middleware for sillo.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from sillo.core.helpers.async_helpers import is_async_callable
from sillo.middleware.base import BaseMiddleware
from sillo.types import Request, Response


class TemplateContextMiddleware(BaseMiddleware):
    """Middleware that injects template context into every request.

    Merges a static default context with an optional async context
    processor, then adds request-specific variables (``request``,
    ``url_for``, ``csrf_token``) into ``request.state.template_context``
    for downstream templates to consume.

    Args:
        default_context: Static dict of variables injected into every
            template. ``None`` becomes an empty dict.
        context_processor: Optional async callable that receives the
            ``Request`` and returns a dict of additional context.
            If sync, it is awaited automatically.
    """

    def __init__(
        self,
        default_context: dict[str, Any] | None = None,
        context_processor: Callable[[Request], Awaitable[dict[str, Any]]] | None = None,
    ):
        """Initialise the template-context middleware.

        Stores the default context and optional processor for use during
        every request.

        Args:
            default_context: Static dict merged into every template.
            context_processor: Async callable that returns per-request
                context variables.
        """
        self.default_context = default_context or {}
        self.context_processor = context_processor

    async def __call__(
        self,
        request: Request,
        response: Response,
        call_next: Callable[..., Awaitable[Any]],
    ) -> Response:
        """Intercept every request, inject template context, and continue.

        Builds the full template context by merging default context,
        the processor's output, and request-level variables, then stores
        the result in ``request.state.template_context``.

        Args:
            request: The incoming HTTP request.
            response: The response object.
            call_next: The next middleware or route handler.

        Returns:
            The response from the downstream handler.
        """
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
    default_context: dict[str, Any] | None = None,
    context_processor: Callable[[Request], Awaitable[dict[str, Any]]] | None = None,
):
    """Factory that returns a ``TemplateContextMiddleware`` instance.

    Convenience function so users can register the middleware without
    importing the class directly::

        app.use(template_context(default_context={"site_name": "MyApp"}))

    Args:
        default_context: Static default context dict.
        context_processor: Optional per-request context callable.

    Returns:
        A configured ``TemplateContextMiddleware`` instance.
    """
    return TemplateContextMiddleware(default_context, context_processor)
