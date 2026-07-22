from __future__ import annotations

import functools
import inspect
import warnings
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class DeprecatedError(FutureWarning):
    """Warning class emitted when deprecated functionality is invoked.

    Subclass of ``FutureWarning`` used to signal that a function, method,
    or parameter has been deprecated and will be removed in a future
    release of the sillo framework. This warning is issued at runtime
    when deprecated code paths are exercised, allowing developers to
    identify and update their usage before the removal deadline.

    Attributes:
        message: A human-readable description of the deprecation, including
            the version it was deprecated in and the version it will be
            removed in.
    """

    pass


def warn_deprecated(
    message: str,
    version: str,
    removed_in: str,
    stacklevel: int = 3,
) -> None:
    """Emit a deprecation warning with version and removal information.

    Issues a ``DeprecatedError`` warning to the Python warnings system,
    formatted with the sillo version context and the version in which the
    deprecated feature will be removed. The warning is directed at the
    caller's stack frame so that the warning points to the user's code
    rather than internal framework code.

    Args:
        message: A human-readable description of what is deprecated and
            any guidance on migration or replacement.
        version: The sillo version string in which the deprecation was
            introduced (e.g. ``"0.5.0"``).
        removed_in: The sillo version string in which the deprecated
            feature is scheduled to be removed (e.g. ``"1.0.0"``).
        stacklevel: The number of stack frames to ascend when emitting
            the warning. Defaults to 3 so the warning points to the
            end-user's calling code.

    Returns:
        None.
    """
    warnings.warn(
        f"[sillo {version}] {message} (will be removed in {removed_in})",
        DeprecatedError,
        stacklevel=stacklevel,
    )


def deprecated(
    since: str,
    removed_in: str,
    message: str = "",
    replacement: str = "",
) -> Callable[[F], F]:
    """Decorator that marks a function or method as deprecated.

    Wraps the target callable so that every invocation emits a
    ``DeprecatedError`` warning before executing the original logic.
    Supports both synchronous and asynchronous callables: the decorator
    inspects the wrapped function at decoration time and selects the
    appropriate wrapper to preserve the original calling convention.

    Args:
        since: The sillo version string in which the deprecation was
            introduced (e.g. ``"0.5.0"``).
        removed_in: The sillo version string in which the deprecated
            callable is scheduled to be removed (e.g. ``"1.0.0"``).
        message: An optional custom deprecation message. If empty, a
            default message is generated from the function name.
        replacement: An optional string naming the replacement callable
            or API. If provided, it is appended to the warning message.

    Returns:
        A decorator that wraps the target callable with deprecation
        warning behavior while preserving its signature via
        ``functools.wraps``.
    """

    def decorator(func: F) -> F:
        """Build the deprecation-wrapped version of the target callable.

        Constructs the appropriate warning message from the decorator
        parameters and the target function name, then returns either a
        synchronous or asynchronous wrapper depending on whether the
        target is a coroutine function.

        Args:
            func: The target callable to wrap with deprecation behavior.

        Returns:
            The wrapped callable that emits a deprecation warning on
            every invocation before delegating to the original function.
        """
        msg = message or f"`{func.__name__}` is deprecated"
        if replacement:
            msg += f". Use `{replacement}` instead."

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Synchronous wrapper that warns then calls the original function.

            Emits a ``DeprecatedError`` warning via ``warn_deprecated``
            before delegating to the wrapped synchronous function with
            all positional and keyword arguments unchanged.

            Args:
                *args: Positional arguments forwarded to the original function.
                **kwargs: Keyword arguments forwarded to the original function.

            Returns:
                The return value of the original function call.
            """
            warn_deprecated(msg, since, removed_in, stacklevel=2)
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Asynchronous wrapper that warns then awaits the original function.

            Emits a ``DeprecatedError`` warning via ``warn_deprecated``
            before delegating to the wrapped asynchronous function with
            all positional and keyword arguments unchanged.

            Args:
                *args: Positional arguments forwarded to the original function.
                **kwargs: Keyword arguments forwarded to the original function.

            Returns:
                The return value of the awaited original function call.
            """
            warn_deprecated(msg, since, removed_in, stacklevel=2)
            return await func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return wrapper  # type: ignore[return-value]

    return decorator


def deprecate_parameter(
    param_name: str,
    since: str,
    removed_in: str,
    replacement: str = "",
) -> Callable[[F], F]:
    """Decorator that marks a specific parameter of a function as deprecated.

    Wraps the target callable so that a ``DeprecatedError`` warning is
    emitted only when the specified parameter is passed as a keyword
    argument. The original function is still called with all arguments
    unchanged. Supports both synchronous and asynchronous callables by
    inspecting the wrapped function at decoration time.

    Args:
        param_name: The name of the keyword parameter to deprecate.
            The warning is only emitted when this name appears in
            ``kwargs`` at call time.
        since: The sillo version string in which the parameter
            deprecation was introduced (e.g. ``"0.5.0"``).
        removed_in: The sillo version string in which the parameter
            is scheduled to be removed (e.g. ``"1.0.0"``).
        replacement: An optional string naming the replacement parameter
            or API. If provided, it is appended to the warning message.

    Returns:
        A decorator that wraps the target callable with parameter-level
        deprecation warning behavior while preserving its signature via
        ``functools.wraps``.
    """

    def decorator(func: F) -> F:
        msg = f"Parameter `{param_name}` of `{func.__name__}` is deprecated"
        if replacement:
            msg += f". Use `{replacement}` instead."

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if param_name in kwargs:
                warn_deprecated(msg, since, removed_in, stacklevel=2)
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if param_name in kwargs:
                warn_deprecated(msg, since, removed_in, stacklevel=2)
            return await func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return wrapper  # type: ignore[return-value]

    return decorator
