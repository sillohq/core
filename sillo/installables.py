"""The shared contract for application subsystems.

An installable owns the wiring that turns configuration into a ready-to-use
application subsystem: application state, middleware, lifespan hooks and any
other integration it needs.  It deliberately does not replace ``app.use()``;
that API remains the explicit place to order request middleware.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from sillo.application import SilloApp


InstalledT = TypeVar("InstalledT", covariant=True)


class Installable(Protocol[InstalledT]):
    """A named subsystem that can be installed on a :class:`SilloApp`.

    Names are application-local identifiers.  Installing the same name more
    than once is idempotent: Sillo returns the first installed service.  This
    preserves the long-standing ``setup_*`` helper behavior while making the
    installed topology inspectable through :attr:`SilloApp.installations`.
    """

    name: str

    def install(self, app: SilloApp) -> InstalledT:
        """Wire this subsystem into *app* and return its public service."""
