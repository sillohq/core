"""sillo.events.transports — Backend registry and factory.

Maps ``backend="memory"|"redis"|"persistent"|"record"`` to a transport.  Redis
and record transports are imported lazily inside the factory so the base
``events`` package (and ``backend="memory"``) works without ``redis`` or
Tortoise installed.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseTransport

_AVAILABLE = {
    "memory": "sillo.events.transports.memory:MemoryTransport",
}


def register_transport(name: str, dotted_path: str) -> None:
    """Register a custom transport by ``module:Class`` dotted path."""
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

    Raises ``ValueError`` for an unknown backend; ``TransportError`` (from the
    transport) if its optional dependency (redis / tortoise) is missing.
    """
    if backend == "memory":
        from .memory import MemoryTransport

        return MemoryTransport(namespace=namespace, on_error=on_error, loop=loop)

    if backend in ("redis", "persistent"):
        # Imported eagerly here (inside the branch) so a missing redis package
        # only fails when actually requested.
        if backend == "redis":
            from .redis import RedisTransport

            cls = RedisTransport
        else:
            from .persistent import PersistentTransport

            cls = PersistentTransport
        return cls(namespace=namespace, on_error=on_error, loop=loop, **kwargs)

    if backend == "record":
        from .record import RecordTransport

        return RecordTransport(
            namespace=namespace, on_error=on_error, loop=loop, **kwargs
        )

    if backend in _AVAILABLE:
        import importlib

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
    """
    from .record import build_event_message

    return build_event_message()
