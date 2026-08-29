"""Declaring a middleware, and normalising the two forms into one.

A middleware reaches the framework in one of two shapes: a raw ASGI factory,
called as ``factory(next_app, *args, **kwargs)``, or a dispatch function taking
``(ctx, call_next)``. :class:`DefineMiddleware` is the common currency -- a
factory paired with the arguments it will be built with, deferred until the
chain is assembled -- and :func:`wrap_middleware` turns the dispatch form into
that shape by pairing it with the bridge.

The chain builders in ``sillo.application`` and ``sillo.core.routing`` iterate
:class:`DefineMiddleware` instances, so by the time they run there is only one
kind of middleware left to think about.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from sillo.middleware.bridge import ASGIRequestResponseBridge
from sillo.types import ASGIApp, MiddlewareType

#: A callable that returns an ASGI application when given the next one.
MiddlewareFactory = Callable[..., ASGIApp]


class DefineMiddleware:
    """Container that pairs a middleware factory with its positional and keyword arguments.

    This class acts as a deferred middleware descriptor. It stores the middleware
    class (or factory callable) together with the arguments that should be passed
    when the middleware is instantiated. The application iterates over a list of
    ``DefineMiddleware`` instances to build the middleware stack at startup.

    Attributes:
        cls: The middleware factory or class to be instantiated.
        args: Positional arguments forwarded to the middleware constructor.
        kwargs: Keyword arguments forwarded to the middleware constructor.
    """

    def __init__(
        self,
        cls: MiddlewareFactory,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialise the descriptor with a middleware factory and its arguments.

        Stores the middleware class together with any positional and keyword
        arguments that should be forwarded when the middleware is later
        instantiated by the application stack builder.

        Args:
            cls: A callable that produces an ASGI application when invoked with
                the remaining arguments. Typically a middleware class.
            *args: Positional arguments forwarded to ``cls`` at instantiation.
            **kwargs: Keyword arguments forwarded to ``cls`` at instantiation.
        """
        self.cls = cls
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> Iterator[Any]:
        """Yield the middleware components as a three-element tuple.

        Allows the instance to be unpacked into ``(cls, args, kwargs)``, which
        is the format expected by the application's middleware stack builder.

        Returns:
            An iterator over ``(cls, args, kwargs)`` where ``cls`` is the
            middleware factory, ``args`` is a tuple of positional arguments,
            and ``kwargs`` is a dictionary of keyword arguments.
        """
        as_tuple = (self.cls, self.args, self.kwargs)
        return iter(as_tuple)

    def __repr__(self) -> str:
        """Return a developer-friendly string representation of this descriptor.

        The representation includes the middleware class name, all positional
        arguments, and all keyword arguments so that the descriptor can be
        identified at a glance during debugging or logging.

        Returns:
            A string in the form ``DefineMiddleware(MiddlewareName, arg1, ...,
            key=value, ...)`` suitable for debugging output.
        """
        class_name = self.__class__.__name__
        args_strings = [f"{value!r}" for value in self.args]
        option_strings = [f"{key}={value!r}" for key, value in self.kwargs.items()]
        name = getattr(self.cls, "__name__", "")
        args_repr = ", ".join([name] + args_strings + option_strings)
        return f"{class_name}({args_repr})"


def wrap_middleware(middleware_function: MiddlewareType) -> DefineMiddleware:
    """Wrap a dispatch-style middleware function into a ``DefineMiddleware`` instance.

    Creates a ``DefineMiddleware`` descriptor that pairs the
    ``ASGIRequestResponseBridge`` class with the given dispatch middleware
    function. This allows the middleware to be added to the application's
    middleware stack in the standard format expected by the framework.

    Args:
        middleware_function: A dispatch-style middleware callable that accepts
            ``(ctx, call_next)`` and returns an awaitable
            response object.

    Returns:
        A ``DefineMiddleware`` instance wrapping the
        ``ASGIRequestResponseBridge`` with the provided dispatch function
        bound as the ``dispatch`` keyword argument.
    """
    return DefineMiddleware(ASGIRequestResponseBridge, dispatch=middleware_function)
