"""sillo.events.transports — Backend registry and factory.

Maps ``backend="memory"|"redis"|"persistent"|"record"`` to a transport.  Redis
and record transports are imported lazily inside the factory so the base
``events`` package (and ``backend="memory"``) works without ``redis`` or
Tortoise installed.

Use :func:`get_transport` to build a transport directly, or let
:class:`~sillo.events.emitter.EventEmitter` call it for you.  Register your own
backend with :func:`register_transport`.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Optional

from .base import BaseTransport
from .memory import MemoryTransport
from .persistent import PersistentTransport
from .record import RecordTransport, build_event_message
from .redis import RedisTransport

# Built-in backends.  Only ``memory`` is eagerly known; redis / persistent /
# record are resolved inside get_transport so their heavy imports stay lazy.
_AVAILABLE = {
    "memory": "sillo.events.transports.memory:MemoryTransport",
}


def register_transport(name: str, dotted_path: str) -> None:
    """Register a custom transport by ``module:Class`` dotted path.

    Args:
        name: Backend identifier used with ``backend=`` / ``get_transport``.
        dotted_path: Import path like ``"myapp.transports:KafkaTransport"``.

    Example:
        >>> register_transport("kafka", "myapp.transports:KafkaTransport")
        >>> get_transport("kafka")
    """
    _AVAILABLE[name] = dotted_path


def get_transport(
    backend: str = "memory",
    *,
    namespace: str = "",
    on_error=None,
    loop=None,
    **kwargs: Any,
) -> BaseTransport:
    """Instantiate a transport by name.

    Args:
        backend: One of ``"memory"``, ``"redis"``, ``"persistent"``,
            ``"record"``, or a name registered via :func:`register_transport`.
        namespace: Channel prefix forwarded to the transport.
        on_error: Optional listener-error callback.
        loop: Optional event loop for background tasks.
        **kwargs: Backend-specific options (e.g. ``url=``, ``max_retries=``).

    Returns:
        A :class:`~sillo.events.transports.base.BaseTransport` instance.

    Raises:
        ValueError: for an unknown backend name.
        TransportError: from the transport if its optional dependency
            (``redis`` / ``tortoise-orm``) is missing.
    """
    if backend == "memory":
        return MemoryTransport(namespace=namespace, on_error=on_error, loop=loop)

    if backend in ("redis", "persistent"):
        if backend == "redis":
            cls = RedisTransport
        else:
            cls = PersistentTransport
        return cls(namespace=namespace, on_error=on_error, loop=loop, **kwargs)

    if backend == "record":
        return RecordTransport(
            namespace=namespace, on_error=on_error, loop=loop, **kwargs
        )

        if backend in _AVAILABLE:
            module_path, _, attr = _AVAILABLE[backend].partition(":")
            module = importlib.import_module(module_path)
        cls = getattr(module, attr)
        return cls(namespace=namespace, on_error=on_error, loop=loop, **kwargs)

    raise ValueError(
        f"Unknown event backend {backend!r}. "
        f"Available: memory, redis, persistent, record"
    )


def setup_event_record() -> Any:
    """Build the ``EventMessage`` model and return it.

    Call once after ``setup_record(...)`` and add the returned class to your
    ``model_modules`` before Tortoise init, OR register it directly::

        from sillo.events.transports.record import setup_event_record
        EventMessage = setup_event_record()  # importable from your models module

    Returns:
        The concrete ``EventMessage`` Tortoise model (also assigned to the
        module-level :data:`~sillo.events.transports.record.EventMessage` so
        :class:`~sillo.events.transports.record.RecordTransport` can find it).

    Raises:
        TransportError: indirectly, if ``sillo.record`` / Tortoise is not
            configured — the underlying import of ``sillo.record.Model`` fails.
    """
    return build_event_message()
