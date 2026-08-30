"""
sillo.helpers.registry — the instance a setup function just built, reachable
from anywhere.

Several subsystems work the same way: ``setup_x(app, config)`` builds one
long-lived instance and puts it on ``app.state``, and code deep inside a
handler, a background job, or a script wants it back. Reaching through
``ctx.base_app.state["x"]`` only works when there is a request in hand,
needs it threaded down to wherever the lookup happens, and is untyped and
keyed by a string every subsystem picks independently (``"storage"``,
``"mail_client"``, ``"record"``, ...).

This is deliberately not request-scoped and has nothing to do with the request
lifecycle: ``setup_x`` registers the instance once, at startup, and it stays
registered for the life of the process — reachable from a request handler, a
queue worker, a scheduled job, or a script that just imported the module,
identically. The framework's own assumption throughout — one instance per
subsystem per application — is what makes "the one most recently registered"
the right answer everywhere it is asked.

Asking before anything registered is a loud :class:`NotConfiguredError`,
naming the setup call that was skipped, rather than ``None`` accepted as if it
were a valid value.
"""

from __future__ import annotations

from typing import Generic, TypeVar

__all__ = ["InstanceRegistry", "NotConfiguredError"]

T = TypeVar("T")


class NotConfiguredError(RuntimeError):
    """Raised when a registered instance is asked for before it exists."""


_NOT_CONFIGURED = """No {what} has been set up yet.

This reads the {what} {setup} registers. Call it during startup, before
anything asks for the {what} back:

    {example}

If it already runs somewhere, check that this code path executes after it —
module import order, not request order, decides whether that has happened.
"""


class InstanceRegistry(Generic[T]):
    """Holds the most recently registered instance of one subsystem.

    A subsystem builds one of these at module scope, registers from its own
    ``setup_x`` function, and reads it back from a small module-level function
    such as ``current_storage()``. There is no per-request or per-task
    scoping — this is a plain slot, filled once at startup and read from
    wherever, exactly like the module-level singletons it replaces.

    Args:
        label: A short name for what this holds, used only in error messages
            (e.g. ``"storage"``).
    """

    __slots__ = ("_instance", "_label")

    def __init__(self, label: str) -> None:
        """Build an empty registry.

        Args:
            label: A short name for what this holds.
        """
        self._label = label
        self._instance: T | None = None

    def register(self, instance: T) -> None:
        """Record *instance* as the one to hand back from now on.

        Args:
            instance: What ``setup_x`` built.
        """
        self._instance = instance

    def current(self, *, setup: str, example: str) -> T:
        """The registered instance.

        Args:
            setup: The setup function's name, e.g. ``"setup_storage"``.
            example: One line showing that function called.

        Returns:
            The registered instance.

        Raises:
            NotConfiguredError: If nothing has been registered yet.
        """
        if self._instance is None:
            raise NotConfiguredError(
                _NOT_CONFIGURED.format(what=self._label, setup=setup, example=example)
            )
        return self._instance
