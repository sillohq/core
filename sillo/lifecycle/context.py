from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any, Dict, Optional


_current_context: ContextVar[Optional["RequestContext"]] = ContextVar(
    "_sillo_request_ctx", default=None
)


class RequestContext:
    """Request-scoped context manager for tracking request lifecycle state.

    Provides a dict-like namespace tied to the current request, accessible
    anywhere in the request handling chain via ``RequestContext.current()``.

    Usage::

        with RequestContext() as ctx:
            ctx["start_time"] = time.monotonic()
            ...
            elapsed = time.monotonic() - ctx["start_time"]
    """

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._token = None

    @classmethod
    def current(cls) -> Optional["RequestContext"]:
        return _current_context.get()

    def __enter__(self) -> "RequestContext":
        self._token = _current_context.set(self)
        return self

    def __exit__(self, *args: Any) -> None:
        _current_context.reset(self._token)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    @property
    def data(self) -> Dict[str, Any]:
        return self._data
