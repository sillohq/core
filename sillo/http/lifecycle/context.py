from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any, Dict, Optional


_current_context: ContextVar[Optional["RequestContext"]] = ContextVar(
    "_sillo_request_ctx", default=None
)
"""Module-level context variable that holds the active RequestContext for the
current async task. Defaults to ``None`` when no request context is active."""


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
        """Initialize a new RequestContext with an empty data namespace.

        Creates an isolated key-value store for the lifetime of a single
        request. The context is not yet active until ``__enter__`` is
        called (i.e. when used as a context manager).

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        self._data: Dict[str, Any] = {}
        self._token = None

    @classmethod
    def current(cls) -> Optional["RequestContext"]:
        """Retrieve the active RequestContext for the current async task.

        Looks up the module-level ``ContextVar`` and returns whichever
        ``RequestContext`` instance was most recently entered on this
        task's context stack. Returns ``None`` when no context is active,
        which typically means the call site is outside a request lifecycle.

        Args:
            None.

        Returns:
            Optional[RequestContext]: The currently active context, or
                ``None`` if no ``RequestContext`` has been entered.

        Raises:
            None.
        """
        return _current_context.get()

    def __enter__(self) -> "RequestContext":
        """Activate this context on the current async task's context stack.

        Sets this instance as the value of the module-level ``ContextVar``
        and stores the reset token so that ``__exit__`` can restore the
        previous value. Supports nested contexts by preserving the prior
        context and restoring it on exit.

        Args:
            None.

        Returns:
            RequestContext: This same instance, now active on the
                context stack, for use inside the ``with`` block.

        Raises:
            None.
        """
        self._token = _current_context.set(self)
        return self

    def __exit__(self, *args: Any) -> None:
        """Deactivate this context and restore the previous context value.

        Called automatically when the ``with`` block exits (normally or
        via exception). Uses the token captured during ``__enter__`` to
        reset the ``ContextVar`` to whatever value it held before this
        context was entered, correctly handling nested contexts.

        Args:
            *args: The standard ``sys.exc_info()`` tuple
                ``(exc_type, exc_val, exc_tb)`` passed by the Python
                runtime on abnormal exits, or ``(None, None, None)``
                on normal exit.

        Returns:
            None.

        Raises:
            None.
        """
        _current_context.reset(self._token)  # ty: ignore[invalid-argument-type]

    def __getitem__(self, key: str) -> Any:
        """Retrieve a value from the context's data namespace by key.

        Provides dict-style bracket access (``ctx["key"]``) to the
        underlying data store. Raises ``KeyError`` if the key does not
        exist, matching standard dict semantics.

        Args:
            key (str): The string key to look up in the context's
                internal data dictionary.

        Returns:
            Any: The value associated with the given key.

        Raises:
            KeyError: If ``key`` is not present in the context data.
        """
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Store a value in the context's data namespace under the given key.

        Provides dict-style bracket assignment (``ctx["key"] = value``)
        to the underlying data store. Overwrites any existing value
        associated with the same key.

        Args:
            key (str): The string key under which to store the value.
            value (Any): The value to associate with the key. Can be
                any Python object.

        Returns:
            None.

        Raises:
            None.
        """
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        """Remove a key-value pair from the context's data namespace.

        Provides dict-style deletion (``del ctx["key"]``) on the
        underlying data store. Raises ``KeyError`` if the key does not
        exist, matching standard dict semantics.

        Args:
            key (str): The string key to remove from the context's
                internal data dictionary.

        Returns:
            None.

        Raises:
            KeyError: If ``key`` is not present in the context data.
        """
        del self._data[key]

    def __contains__(self, key: str) -> bool:
        """Check whether a key exists in the context's data namespace.

        Supports the ``in`` operator (``"key" in ctx``) for convenient
        membership testing against the underlying data store.

        Args:
            key (str): The string key to check for existence in the
                context's internal data dictionary.

        Returns:
            bool: ``True`` if the key is present, ``False`` otherwise.

        Raises:
            None.
        """
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the context, returning a default if absent.

        Safe accessor that never raises ``KeyError``. If the requested
        key is not found in the data store, the provided default value
        is returned instead, mirroring ``dict.get`` semantics.

        Args:
            key (str): The string key to look up in the context's
                internal data dictionary.
            default (Any, optional): The fallback value to return when
                ``key`` is not found. Defaults to ``None``.

        Returns:
            Any: The value associated with ``key``, or ``default`` if
                the key is not present.

        Raises:
            None.
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a value in the context using an explicit method call.

        Functional equivalent of ``__setitem__`` for callers that prefer
        a named method over bracket syntax. Overwrites any existing
        value associated with the same key.

        Args:
            key (str): The string key under which to store the value.
            value (Any): The value to associate with the key. Can be
                any Python object.

        Returns:
            None.

        Raises:
            None.
        """
        self._data[key] = value

    @property
    def data(self) -> Dict[str, Any]:
        """Return a reference to the context's internal data dictionary.

        Exposes the raw underlying storage for iteration, bulk reads,
        or serialization. Callers should be aware that mutations to the
        returned dict directly affect the context's state.

        Args:
            None.

        Returns:
            Dict[str, Any]: The internal data dictionary containing all
                key-value pairs stored in this context.

        Raises:
            None.
        """
        return self._data
