"""The middleware contract: one context, one ``call_next``.

A middleware is any object with::

    async def __call__(self, ctx, call_next) -> Any

:class:`BaseMiddleware` supplies that ``__call__`` and hands the work to
:meth:`~BaseMiddleware.dispatch`, which subclasses override::

    from sillo import BaseMiddleware, redirect

    class RequireLogin(BaseMiddleware):
        async def dispatch(self, ctx, call_next):
            if ctx.user is None:
                return redirect("/login")     # stop here, send this
            response = await call_next()      # or continue down the chain
            response.headers["x-checked"] = "1"
            return response

Returning a response object without awaiting ``call_next`` short-circuits the
chain: nothing further down runs, and what was returned is what the client
gets. Responses are built by the free helpers in ``sillo`` -- ``json``,
``html``, ``text``, ``redirect``, ``file``, ``stream`` -- not by a response
object handed in as an argument.
"""

from __future__ import annotations

import typing
from typing import Annotated

from typing_extensions import Any, Doc

from sillo.core.http import HttpContext

CallNext = typing.Callable[[], typing.Awaitable[Any]]


class BaseMiddleware:
    """Base class for context middleware.

    Subclasses override :meth:`dispatch`. The default implementation simply
    continues the chain, so a subclass that overrides nothing is a no-op.
    """

    def __init__(
        self,
        **kwargs: Annotated[
            dict[typing.Any, typing.Any],
            Doc("Additional keyword arguments for middleware configuration."),
        ],
    ) -> None:
        """Initialise the middleware.

        Accepts arbitrary keyword arguments so subclasses can take configuration
        without each having to define a constructor.

        Args:
            **kwargs: Arbitrary keyword arguments for middleware settings.
        """

    async def __call__(
        self,
        ctx: Annotated[
            HttpContext,
            Doc("The context for the connection being handled."),
        ],
        call_next: Annotated[
            CallNext,
            Doc("Awaits the rest of the chain and returns its response."),
        ],
    ) -> Any:
        """Run this middleware for one request.

        Args:
            ctx: The context for the connection being handled.
            call_next: Awaits the next middleware or the route handler.

        Returns:
            Whatever :meth:`dispatch` returns -- a response object to send, or
            the value produced by ``call_next``.
        """
        return await self.dispatch(ctx, call_next)

    async def dispatch(
        self,
        ctx: Annotated[
            HttpContext,
            Doc("The context for the connection being handled."),
        ],
        call_next: Annotated[
            CallNext,
            Doc("Awaits the rest of the chain and returns its response."),
        ],
    ) -> Any:
        """Handle one request. Override this.

        Return a response object to answer immediately without running the rest
        of the chain, or ``await call_next()`` to continue and optionally act on
        what comes back.

        Args:
            ctx: The context for the connection being handled.
            call_next: Awaits the next middleware or the route handler.

        Returns:
            A response object, or the result of ``call_next``.
        """
        return await call_next()
