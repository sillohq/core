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

import inspect
from collections.abc import Callable, Iterator
from typing import Any, cast

from sillo.middleware.bridge import ASGIRequestResponseBridge
from sillo.types import ASGIApp, MiddlewareType

#: A callable that returns an ASGI application when given the next one.
MiddlewareFactory = Callable[..., ASGIApp]


def _runtime_call_signature(
    middleware: MiddlewareType | MiddlewareFactory | ASGIApp,
) -> inspect.Signature | None:
    """Return the signature that governs how `middleware` is actually called.

    A class registered with `use()` is a *factory*: sillo constructs an
    instance of it (`cls(next_app, *args, **kwargs)`) and it is that
    instance's `__call__` -- not the class's `__init__`, which is what
    `inspect.signature` reads for a class by default -- that runs per
    request. `getattr(cls, "__call__", None)` is used rather than
    `cls.__dict__.get("__call__")` so an `__call__` inherited from a base
    class (as opposed to one only ever present on `object`, i.e. not
    overridden at all) is found by walking the MRO the same way Python does
    when it actually calls the instance.

    Anything that isn't a class -- an instance, a bound method, a plain
    function, a `functools.partial` -- is called directly as-is, so its own
    signature is what matters. `inspect.unwrap` strips any `functools.wraps`
    decoration first so a decorated middleware doesn't get misread as
    `(*args, **kwargs)`.

    Returns `None` when no such signature can be determined at all, which
    callers must treat as "no structural signal either way."
    """
    if inspect.isclass(middleware):
        # Not the `hasattr(x, "__call__")` anti-pattern `callable()` replaces:
        # the object fetched here is inspected for its signature, not just
        # tested for truthiness, and `callable(middleware)` would answer
        # about the class itself (always true; classes are callable) rather
        # than about what its *instances* -- what `use()` actually ends up
        # calling -- will be.
        target = getattr(middleware, "__call__", None)  # noqa: B004
        if target is None or target is object.__call__:
            return None
    elif callable(middleware):
        target = middleware
    else:
        return None

    try:
        return inspect.signature(inspect.unwrap(target))
    except (TypeError, ValueError):
        return None


def _required_positional_count(
    middleware: MiddlewareType | MiddlewareFactory | ASGIApp,
) -> int | None:
    """Count `middleware`'s own required positional parameters.

    Shared by every shape check in this module: how many arguments a
    callable's signature demands, with no default and not swallowed by
    `*args`, is the one structural signal available for telling ASGI's
    `(scope, receive, send)` from sillo's dispatch `(ctx, call_next)` from a
    factory's `(next_app, ...)`, regardless of what its author named them.

    Returns `None` when no signature can be read at all (see
    `_runtime_call_signature`), or when a bare `*args` could swallow any
    number of positional arguments -- both are "no structural signal",
    which callers must treat as neither shape rather than guessing.
    """
    sig = _runtime_call_signature(middleware)
    if sig is None:
        return None

    positional_kinds = (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    params = [p for p in sig.parameters.values() if p.name not in ("self", "cls")]
    if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params):
        return None
    return sum(
        1
        for p in params
        if p.kind in positional_kinds and p.default is inspect.Parameter.empty
    )


def _is_raw_asgi_middleware(
    middleware: MiddlewareType | MiddlewareFactory | ASGIApp,
) -> bool:
    """Guess whether `middleware` is a raw ASGI factory rather than dispatch.

    The two calling conventions `use()` accepts -- ASGI's `(scope, receive,
    send)` and sillo's dispatch `(ctx, call_next)` -- are both called with
    every argument positional and none defaulted. That makes the *count* of
    required positional parameters the signal to read: three is ASGI, two is
    dispatch.

    A signature with no structural signal either way is left as dispatch --
    the pre-existing default -- and `use()` separately raises if that guess
    turns out to be wrong and factory arguments were also passed, rather than
    silently misrouting them.
    """
    return _required_positional_count(middleware) == 3


def _is_prebuilt_raw_instance(
    middleware: MiddlewareType | MiddlewareFactory | ASGIApp,
) -> bool:
    """Whether a raw `middleware` is already a built ASGI app, not a factory.

    `use(mw, raw=True)` accepts a factory still awaiting `next_app` -- a
    class, built as `cls(next_app, *args, **kwargs)`, or a plain function
    such as ``def mw(app): ...; return inner`` -- or an already-configured
    instance, as in ``app.use(SessionMiddleware(secret_key=...))``. A class
    is never already built, so it is ruled out first. Otherwise, the same
    required-positional-parameter count that tells ASGI from dispatch in
    `_is_raw_asgi_middleware` also tells a bare factory from a live instance
    here: a factory's own signature takes the next app (and maybe more,
    typically one required parameter), while an instance ready to run has a
    `__call__` already shaped like the ASGI app it is -- exactly three
    required positional parameters (`scope, receive, send`), no more and no
    fewer.
    """
    if inspect.isclass(middleware):
        return False
    return _required_positional_count(middleware) == 3


def _rebinding_factory(instance: ASGIApp) -> MiddlewareFactory:
    """Wrap an already-constructed raw ASGI middleware as a one-shot factory.

    `_build_request_chain` calls every raw entry as `cls(next_app, *args,
    **kwargs)` -- the ASGI convention, which assumes `cls` is still waiting
    to be built. `app.use(SessionMiddleware(secret_key=...))` and every other
    built-in registered the same way pass an instance instead, already
    configured and with nowhere to put `next_app` except by setting `.app` on
    it directly -- which each of those sets to `None` at construction for
    exactly this. Third-party raw ASGI middleware registered the same way is
    expected to do likewise; one without a settable `.app` fails here with an
    `AttributeError` naming the instance, which is a clearer signal than the
    `TypeError` calling it as a factory would have raised instead.

    `instance` is typed as the `ASGIApp` it already is, not the factory it is
    about to be wrapped as -- `.app` is set on it with `setattr` rather than
    attribute access because nothing in the `ASGIApp` shape (just `(scope,
    receive, send) -> Awaitable`) promises that attribute exists; the
    `AttributeError` this raises when it does not is the point.
    """

    def factory(app: ASGIApp) -> ASGIApp:
        setattr(instance, "app", app)  # noqa: B010
        return instance

    return cast(MiddlewareFactory, factory)


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
