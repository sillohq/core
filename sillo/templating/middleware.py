"""
Template context middleware for sillo.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from sillo.core.helpers.async_helpers import is_async_callable
from sillo.middleware.base import BaseMiddleware
from sillo.types import HttpContext


class TemplateContextMiddleware(BaseMiddleware):
    """Middleware that injects template context into every request.

    Merges a static default context with an optional async context
    processor, then adds context-derived variables (``ctx``,
    ``url_for``, ``csrf_token``) into ``ctx.state.template_context``
    for downstream templates to consume.

    Args:
        default_context: Static dict of variables injected into every
            template. ``None`` becomes an empty dict.
        context_processor: Optional async callable that receives the
            ``HttpContext`` and returns a dict of additional context.
            If sync, it is awaited automatically.
    """

    def __init__(
        self,
        default_context: dict[str, Any] | None = None,
        context_processor: Callable[[HttpContext], Awaitable[dict[str, Any]]]
        | None = None,
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

    async def dispatch(
        self,
        ctx: HttpContext,
        call_next: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Intercept every request, inject template context, and continue.

        Builds the full template context by merging default context,
        the processor's output, and context-derived variables, then stores
        the result in ``ctx.state.template_context``.

        Args:
            ctx: The context for the request being handled.
            call_next: The next middleware or route handler.

        Returns:
            The response from the downstream handler.
        """
        context = self.default_context.copy()

        if self.context_processor:
            if not is_async_callable(self.context_processor):
                per_request = self.context_processor(ctx)
            else:
                per_request = await self.context_processor(ctx)
            context.update(per_request)  # ty :ignore[no-matching-overload]

        context.update(
            {
                "ctx": ctx,
                "url_for": ctx.base_app.url_for,
                # Only present when CSRFMiddleware is installed. Reading it
                # directly made every template render raise AttributeError in
                # an application that had not turned CSRF on.
                "csrf_token": getattr(ctx.state, "csrf_token", None),
            }
        )

        ctx.state.template_context = context
        return await call_next()


def template_context(
    default_context: dict[str, Any] | None = None,
    context_processor: Callable[[HttpContext], Awaitable[dict[str, Any]]] | None = None,
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
