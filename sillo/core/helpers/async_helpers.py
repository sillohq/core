"""sillo.helpers.async_helpers — Async introspection and awaitable utilities.

Small, dependency-free helpers used across sillo to detect async callables
and wrap coroutines so they behave as both awaitables and async context
managers. Import from ``sillo.helpers.async_helpers``.
"""

from __future__ import annotations

import functools
import inspect
import sys
import typing
from contextlib import AbstractContextManager, ContextDecorator
from types import TracebackType
from typing import TypeGuard

has_exceptiongroups = True
if sys.version_info < (3, 11):  # pragma: no cover
    try:
        from exceptiongroup import BaseExceptionGroup
    except ImportError:
        has_exceptiongroups = False

T = typing.TypeVar("T")
AwaitableCallable = typing.Callable[..., typing.Awaitable[T]]


@typing.overload
def is_async_callable(obj: AwaitableCallable[T]) -> TypeGuard[AwaitableCallable[T]]: ...


@typing.overload
def is_async_callable(obj: typing.Any) -> TypeGuard[AwaitableCallable[typing.Any]]: ...


def is_async_callable(obj: typing.Any) -> typing.Any:
    """Determine whether the given object is an async callable.

    Unwraps :class:`functools.partial` wrappers to inspect the underlying
    function, then checks whether it is a coroutine function or a callable
    object whose ``__call__`` method is a coroutine function. Used
    throughout sillo to decide whether to ``await`` a handler or call it
    synchronously.

    Args:
        obj: Any Python object to inspect. Typically a function, method,
            callable class instance, or :class:`functools.partial` wrapping
            one of these.

    Returns:
        ``True`` if the object (after unwrapping partials) is a coroutine
        function or a callable whose ``__call__`` is a coroutine function,
        ``False`` otherwise. The return type uses :class:`TypeGuard` for
        static type narrowing.

    Raises:
        No exceptions are raised during inspection.
    """
    while isinstance(obj, functools.partial):
        obj = obj.func

    return inspect.iscoroutinefunction(obj) or (
        callable(obj) and inspect.iscoroutinefunction(obj.__call__)
    )


T_co = typing.TypeVar("T_co", covariant=True)


class AwaitableOrContextManager(
    typing.Awaitable[T_co], typing.AsyncContextManager[T_co], typing.Protocol[T_co]
):
    """Protocol for objects that are both awaitable and async context managers.

    Defines the interface for objects that can be used in two ways: either
    directly awaited to obtain a result, or used as an async context manager
    with ``async with`` syntax. This dual interface is used by sillo's
    lifespan and startup/shutdown handlers to support both calling patterns.

    Attributes:
        T_co: The covariant type parameter representing the value produced
            when the object is awaited or entered as a context manager.
    """


class SupportsAsyncClose(typing.Protocol):
    """Protocol for objects that support an async ``close`` method.

    Defines the minimal interface required for objects that need to be
    cleaned up asynchronously, typically used by
    :class:`AwaitableOrContextManagerWrapper` to ensure the wrapped
    object's ``close`` method is called when exiting the context manager.
    """

    async def close(self) -> None:
        """Close the resource asynchronously, releasing any held resources.

        This method should be implemented by concrete classes to perform
        cleanup operations such as closing connections, releasing file
        handles, or stopping background tasks.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            None. This method performs cleanup and does not return a value.

        Raises:
            Implementations may raise exceptions if cleanup fails; the
            specific exceptions depend on the concrete implementation.
        """
        ...  # pragma: no cover


SupportsAsyncCloseType = typing.TypeVar(
    "SupportsAsyncCloseType", bound=SupportsAsyncClose, covariant=False
)


class AwaitableOrContextManagerWrapper(typing.Generic[SupportsAsyncCloseType]):
    """Wrapper that makes an awaitable usable as both an awaitable and async context manager.

    Wraps an awaitable that resolves to an object supporting async close,
    allowing the caller to either ``await`` the result directly or use
    ``async with`` syntax for automatic cleanup. The wrapper ensures that
    ``close()`` is called on the resolved object when used as a context
    manager.

    Attributes:
        aw: The underlying awaitable that produces the context manager target.
        entered: The resolved object after entering the async context.
    """

    __slots__ = ("aw", "entered")

    def __init__(self, aw: typing.Awaitable[SupportsAsyncCloseType]) -> None:
        """Initialize the wrapper with an awaitable that resolves to a closeable object.

        Stores the awaitable for later use when either ``__await__`` or
        ``__aenter__`` is called. The awaitable is not consumed until
        one of these methods is invoked.

        Args:
            aw: An awaitable object (e.g. a coroutine) that resolves to
                an object implementing the :class:`SupportsAsyncClose`
                protocol with an async ``close`` method.

        Returns:
            None. This is a constructor and does not return a value.

        Raises:
            No exceptions are raised during initialization.
        """
        self.aw = aw

    def __await__(self) -> typing.Generator[typing.Any, None, SupportsAsyncCloseType]:
        """Await the underlying awaitable and return the resolved object directly.

        Delegates to the wrapped awaitable's ``__await__`` method, allowing
        the wrapper to be used in ``await`` expressions. Note that when
        used this way, ``close()`` is NOT called automatically; the caller
        is responsible for cleanup.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A generator that yields control to the event loop and resolves
            to the object produced by the underlying awaitable.

        Raises:
            Any exception raised by the underlying awaitable is propagated
            unchanged to the caller.
        """
        return self.aw.__await__()

    async def __aenter__(self) -> SupportsAsyncCloseType:
        """Enter the async context by awaiting the underlying awaitable.

        Awaits the wrapped awaitable and stores the resolved object so
        that ``close()`` can be called on it during ``__aexit__``. This
        enables the ``async with`` usage pattern with automatic cleanup.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            The resolved object produced by the underlying awaitable,
            which implements :class:`SupportsAsyncClose`.

        Raises:
            Any exception raised by the underlying awaitable is propagated
            unchanged to the caller.
        """
        self.entered = await self.aw
        return self.entered

    async def __aexit__(self, *args: object) -> bool | None:
        """Exit the async context by closing the resolved object.

        Calls the ``close()`` method on the object that was resolved
        during ``__aenter__``, ensuring proper cleanup of resources
        regardless of whether an exception occurred in the context body.

        Args:
            *args: The exception information ``(exc_type, exc_val, exc_tb)``
                passed by the async context manager protocol. These are
                accepted but not inspected; exceptions are not suppressed.

        Returns:
            Always returns ``None``, meaning exceptions are never
            suppressed by this context manager.

        Raises:
            Any exception raised by the ``close()`` method of the resolved
            object is propagated to the caller.
        """
        await self.entered.close()
        return None


class _CollapseExcGroups(ContextDecorator):
    """Unwrap single-exception exception groups as they leave the ``with`` block.

    A class rather than a ``@contextmanager`` generator: this runs twice for
    every request, and building, entering and finishing a generator each time
    is measurable next to the few nanoseconds of work it actually does. The
    behaviour is the generator's, exactly: the exception that leaves the block
    is the innermost one when a chain of one-element groups wraps it, and any
    other exception propagates untouched.
    """

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc is None or not has_exceptiongroups:
            return False
        inner = exc
        while isinstance(inner, BaseExceptionGroup) and len(inner.exceptions) == 1:  # ty: ignore[unresolved-attribute]
            inner = inner.exceptions[0]  # ty: ignore[unresolved-attribute]  # pragma: no cover
        if inner is not exc:
            # `raise inner`, not a bare re-raise: the original is still the
            # in-flight exception, and the point is to replace it.
            raise inner
        return False


_COLLAPSE_EXCGROUPS = _CollapseExcGroups()


def collapse_excgroups() -> AbstractContextManager[None]:
    """Context manager that unwraps single-exception exception groups on raise.

    When running on Python versions that support exception groups (3.11+),
    this context manager catches any :class:`BaseExceptionGroup` with
    exactly one nested exception and re-raises that inner exception
    directly, collapsing the group. On older Python versions or when the
    ``exceptiongroup`` backport is not installed, exceptions pass through
    unchanged.

    Returns:
        A context manager that yields ``None``. It holds no state, so one
        instance is shared and may be nested or used concurrently.

    Raises:
        BaseException: Re-raises whatever exception occurred inside the
        ``with`` block, potentially unwrapped from a single-element
        exception group if applicable.
    """
    return _COLLAPSE_EXCGROUPS
