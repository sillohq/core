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
    """Register a custom transport backend by its ``module:Class`` dotted path.

    Adds a new entry to the internal backend registry so that subsequent calls
    to :func:`get_transport` can resolve the backend by *name*.  The transport
    class is not imported at registration time; it is lazily resolved when
    :func:`get_transport` is first called with the matching name, keeping
    startup cost minimal and avoiding hard import errors for optional
    dependencies.

    If *name* collides with an already-registered backend (built-in or custom),
    the previous mapping is silently overwritten, allowing applications to
    replace built-in backends with patched or instrumented variants.

    Args:
        name: Backend identifier used with the ``backend=`` parameter of
            :func:`get_transport` or :class:`~sillo.events.emitter.EventEmitter`.
            Should be a short, lowercase string (e.g. ``"kafka"``).
        dotted_path: Fully-qualified import path in ``"module:ClassName"``
            format, for example ``"myapp.transports:KafkaTransport"``.  The
            module must be importable and the attribute must be a subclass of
            :class:`~sillo.events.transports.base.BaseTransport`.

    Raises:
        ValueError: If *dotted_path* does not contain a colon separator.
        ImportError: Raised lazily by :func:`get_transport` if the module
            cannot be imported when the backend is first requested.

    Example:
        >>> register_transport("kafka", "myapp.transports:KafkaTransport")
        >>> transport = get_transport("kafka")
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
    """Instantiate and return a transport backend by name.

    Factory function that resolves *backend* to the appropriate
    :class:`~sillo.events.transports.base.BaseTransport` subclass, constructs
    it with the supplied parameters, and returns the ready-to-use instance.
    Built-in backends (``memory``, ``redis``, ``persistent``, ``record``) are
    handled directly; custom backends registered via :func:`register_transport`
    are resolved lazily through their dotted import path.

    The ``memory`` backend is the default and requires no additional
    dependencies.  Networked backends (``redis``, ``persistent``) accept
    extra keyword arguments such as ``url`` and ``max_retries`` which are
    forwarded to the transport constructor.

    Args:
        backend: Name of the backend to instantiate.  One of ``"memory"``,
            ``"redis"``, ``"persistent"``, ``"record"``, or any name
            previously registered via :func:`register_transport`.  Defaults
            to ``"memory"``.
        namespace: Optional channel prefix forwarded to the transport
            constructor.  When set, all channels are scoped under this
            namespace to avoid cross-application collisions.
        on_error: Optional :data:`~sillo.events.transports.base.ErrorFn`
            callback invoked when a listener raises during dispatch.
        loop: Optional :class:`asyncio.AbstractEventLoop` for scheduling
            background tasks in networked transports.
        **kwargs: Backend-specific keyword arguments forwarded to the
            transport constructor (e.g. ``url=``, ``max_retries=``,
            ``db_key=``).

    Returns:
        A fully constructed :class:`~sillo.events.transports.base.BaseTransport`
        instance ready to be bound to an emitter via ``bind()`` and started.

    Raises:
        ValueError: If *backend* does not match any known or registered
            backend name.  The error message lists all available backends.
        TransportError: Re-raised from the transport constructor if its
            optional dependency (``redis`` / ``tortoise-orm``) is missing
            or the backing service is unreachable.

    Example:
        >>> transport = get_transport("memory")
        >>> transport.name
        'memory'
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

    # Anything registered through register_transport(). This block used to be
    # indented into the `record` branch above, after its unconditional return,
    # so it could never execute: every registered backend fell through to the
    # ValueError below and register_transport() did nothing observable.
    if backend in _AVAILABLE:
        module_path, _, attr = _AVAILABLE[backend].partition(":")
        module = importlib.import_module(module_path)
        cls = getattr(module, attr)
        return cls(namespace=namespace, on_error=on_error, loop=loop, **kwargs)

    raise ValueError(
        f"Unknown event backend {backend!r}. "
        f"Available: {', '.join(sorted({'memory', 'redis', 'persistent', 'record', *_AVAILABLE}))}"
    )


def setup_event_record() -> Any:
    """Build and return the ``EventMessage`` Tortoise ORM model.

    Constructs the concrete ``EventMessage`` model class used by the
    :class:`~sillo.events.transports.record.RecordTransport` to persist
    dispatched events into a relational database via Tortoise ORM.  This
    function must be called once during application startup — after
    ``setup_record(...)`` has configured the record subsystem — and the
    returned class must be added to ``model_modules`` before Tortoise
    initialization, or registered directly with the Tortoise app registry.

    The model is also assigned to the module-level
    :data:`~sillo.events.transports.record.EventMessage` attribute so that
    :class:`~sillo.events.transports.record.RecordTransport` can discover it
    at runtime without requiring an explicit reference.

    Returns:
        The concrete ``EventMessage`` Tortoise model class.  This is a
        fully-formed ORM model with fields for event ID, channel name,
        payload, and timestamp, ready to be registered with Tortoise and
        used for event persistence and querying.

    Raises:
        TransportError: Indirectly, if ``sillo.record`` or Tortoise ORM is
            not installed or not yet configured when this function is called.
            The underlying import of ``sillo.record.Model`` will fail with
            an :class:`ImportError` that is surfaced as a transport error.
        RuntimeError: If called before the record subsystem has been
            initialized via ``setup_record(...)``.

    Example:
        >>> from sillo.events.transports.record import setup_event_record
        >>> EventMessage = setup_event_record()
        >>> EventMessage.__name__
        'EventMessage'
    """
    return build_event_message()
