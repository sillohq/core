"""
Nexios Context Module

Provides request-scoped context management using Python's contextvars.
Allows getting and setting the current context throughout the request lifecycle.
"""

from nexios.dependencies import Context
import contextvars
from typing import Optional

# The context variable storing the current request context
_current_context_var: contextvars.ContextVar[Optional["Context"]] = (
    contextvars.ContextVar("nexios_current_context", default=None)
)


def get_current_context() -> Optional["Context"]:
    """
    Get the current request context.

    Returns:
        The current Context instance, or None if not set.

    Example:
        ```python
        from nexios import get_current_context

        def my_dependency():
            ctx = get_current_context()
            if ctx:
                return ctx.request.headers.get("Authorization")
            return None
        ```
    """
    return _current_context_var.get()


def set_context(ctx: Optional["Context"]) -> contextvars.Token:
    """
    Set the current request context.

    Args:
        ctx: The Context instance to set, or None to clear.

    Returns:
        A token that can be used to reset the context to its previous value.

    Example:
        ```python
        from nexios import get_current_context, set_context

        # Set context
        token = set_context(new_context)

        try:
            # Use context
            ctx = get_current_context()
        finally:
            # Reset to previous value
            set_context(None).var.reset(token)
        ```
    """
    return _current_context_var.set(ctx)


def reset_context(token: contextvars.Token) -> None:
    """
    Reset the context to its previous value using a token from set_context.

    Args:
        token: The token returned by set_context.

    Example:
        ```python
        from nexios import get_current_context, set_context, reset_context

        token = set_context(new_context)
        try:
            ctx = get_current_context()
        finally:
            reset_context(token)
        ```
    """
    _current_context_var.reset(token)


# Re-export Context for convenience

__all__ = [
    "Context",
    "get_current_context",
    "set_context",
    "reset_context",
    "_current_context_var",
]
