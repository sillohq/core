"""
sillo.storage.context — the storage :func:`~sillo.storage.storage.setup_storage`
built, reachable from anywhere.

``setup_storage`` already builds one :class:`~sillo.storage.storage.Storage`
and hands it back; the awkward part was ever afterwards, where a handler in a
routes module either imported the application just to reach ``app.state`` (a
circular import, since the application is what registers the routes) or
threaded the instance through every function signature by hand — including
into queue jobs and scripts, where there is no request to thread it from.

:func:`current_storage` is the other way in: it reads the instance
``setup_storage`` registered at startup, using the shared
:class:`~sillo._internals.registry.InstanceRegistry`. It has nothing to do
with the request lifecycle — a background job or a script reaches for it
exactly the way a handler does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._internals.registry import InstanceRegistry, NotConfiguredError

if TYPE_CHECKING:  # pragma: no cover
    from .storage import Storage

__all__ = ["NotConfiguredError", "current_storage", "register"]

_registry: InstanceRegistry[Storage] = InstanceRegistry("storage")

_EXAMPLE = (
    'storage = setup_storage(app, StorageConfig(default="attachments", buckets={...}))'
)


def register(storage: Storage) -> None:
    """Record *storage* as the one to hand back from now on.

    Called by :func:`~sillo.storage.storage.setup_storage`; there is no
    reason to call this directly outside a test of the registry itself.

    Args:
        storage: What ``setup_storage`` built.
    """
    _registry.register(storage)


def current_storage() -> Storage:
    """The storage ``setup_storage`` registered.

    Returns:
        The registered :class:`~sillo.storage.storage.Storage`.

    Raises:
        NotConfiguredError: If ``setup_storage`` has not run yet.
    """
    return _registry.current(setup="setup_storage", example=_EXAMPLE)
