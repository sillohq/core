"""
sillo Context Module

Provides request-scoped context management using Python's contextvars.
Allows getting and setting the current context throughout the request lifecycle.
"""

import contextvars
from typing import Optional, Any

# The context variable storing the current request context
_current_context_var: contextvars.ContextVar[Optional[Any]] = (
    contextvars.ContextVar("sillo_current_context", default=None)
)


def get_current_context() -> Optional[Any]:
    return _current_context_var.get()


def set_context(ctx: Optional[Any]) -> contextvars.Token:
    return _current_context_var.set(ctx)


def reset_context(token: contextvars.Token) -> None:
    _current_context_var.reset(token)


__all__ = [
    "get_current_context",
    "set_context",
    "reset_context",
    "_current_context_var",
]
