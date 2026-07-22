from __future__ import annotations

import functools
import inspect
import warnings
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class DeprecatedError(FutureWarning):
    pass


def warn_deprecated(
    message: str,
    version: str,
    removed_in: str,
    stacklevel: int = 3,
) -> None:
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
    def decorator(func: F) -> F:
        msg = message or f"`{func.__name__}` is deprecated"
        if replacement:
            msg += f". Use `{replacement}` instead."

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warn_deprecated(msg, since, removed_in, stacklevel=2)
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
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
