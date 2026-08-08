from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, Union
from weakref import ReferenceType, WeakMethod

from .enums import EventPhase

# Exported: sillo.events.core imports this. PYI018 sees an unused private
# TypeVar because nothing in *this* module uses it, which is not the same
# as nothing using it.
_T = TypeVar("_T", bound="EventProtocol")  # noqa: PYI018

# Exported: sillo.events.core imports this. PYI018 flags it as an unused
# private TypeVar because nothing in this module uses it, which is not the
# same as nothing using it.


@dataclass
class EventContext:
    """Context information about a dispatched event.

    Carries metadata that travels with an event through the capture, target,
    and bubble phases of the dispatch pipeline.  The context is immutable after
    construction and is passed alongside the envelope to every listener and
    transport callback so they can make routing, logging, or filtering
    decisions without mutating the event itself.

    The ``source`` attribute holds a reference to the originating emitter or
    object, enabling listeners to introspect *who* fired the event.  The
    ``phase`` field tracks the current propagation stage according to the
    :class:`~sillo.events.enums.EventPhase` enumeration.

    Attributes:
        timestamp: Epoch-seconds float indicating when the event was created.
            Produced by :func:`time.time` at emit time.
        event_id: A globally unique identifier (UUID4 string) assigned by the
            emitter.  Used for de-duplication in networked transports.
        source: Arbitrary reference to the object that originated the event.
            Typically the :class:`~sillo.events.emitter.EventEmitter` instance
            but may be any object the caller chooses to attach.
        phase: The current propagation phase of the event.  Defaults to
            :attr:`EventPhase.AT_TARGET` for simple single-hop dispatch.

    Example:
        >>> ctx = EventContext(
        ...     timestamp=1718000000.0,
        ...     event_id="abc-123",
        ...     source=emitter,
        ... )
        >>> ctx.phase
        <EventPhase.AT_TARGET: ...>
    """

    timestamp: float
    event_id: str
    source: Any
    phase: EventPhase = EventPhase.AT_TARGET


ListenerType = Union[
    Callable[..., Any],
    ReferenceType[Callable[..., Any]],
    WeakMethod[Callable[..., Any]],
]


class EventProtocol(Protocol):
    """Structural protocol defining the interface every event object must satisfy.

    This protocol is used by the serialization mixin, the transport layer, and
    the emitter to interact with event objects without requiring a shared base
    class.  Any class that exposes the four attributes (``name``,
    ``listener_count``, ``max_listeners``, ``enabled``) and the two methods
    (``get_metrics``, ``__call__``) is considered compatible.

    The protocol intentionally mirrors the subset of the full
    :class:`~sillo.events.core.Event` API that external consumers need, keeping
    the coupling surface small and the implementation flexible.

    Attributes:
        name: The channel name this event is registered under.
        listener_count: The current number of listeners attached to the event.
        max_listeners: The upper bound on listeners before the emitter raises
            :class:`~sillo.events.exceptions.MaxListenersExceededError`.
        enabled: Boolean flag indicating whether the event is active.  When
            ``False``, the emitter skips dispatch for this channel.

    Example:
        >>> def accepts_event(ev: EventProtocol) -> str:
        ...     return ev.name
    """

    name: str  # Note: Protocol attributes don't strictly need values but types
    listener_count: int
    max_listeners: int
    enabled: bool

    def get_metrics(self) -> dict[str, Any]:
        """Collect and return a snapshot of the event's runtime metrics.

        The returned dictionary contains counters and timing data accumulated
        during the event's lifetime, such as total dispatch count, average
        listener execution time, and error count.  The exact keys depend on
        the concrete implementation but must be JSON-serializable so the
        serialization mixin can include them in :meth:`to_json` output.

        Returns:
            A dictionary mapping metric names (strings) to their current values.
            Values are typically ``int`` or ``float`` but may include nested
            dicts for histogram-style data.  The dictionary is a fresh copy;
            mutating it does not affect the event's internal state.

        Example:
            >>> metrics = event.get_metrics()
            >>> "dispatch_count" in metrics
            True
        """
        ...

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the event as a callable, dispatching to all registered listeners.

        This method is the primary entry point for triggering event dispatch.
        The emitter calls it when ``emit`` or ``emit_async`` is invoked on a
        channel.  Positional and keyword arguments are forwarded verbatim to
        every registered listener in priority order.

        The return value is implementation-defined.  The default
        :class:`~sillo.events.core.Event` returns a summary dict with
        ``event_id`` and ``listeners_executed`` keys.

        Args:
            *args: Positional arguments forwarded to each listener.
            **kwargs: Keyword arguments forwarded to each listener.

        Returns:
            Implementation-defined dispatch result.  Typically a dict containing
            at least ``event_id`` (str) and ``listeners_executed`` (int).

        Raises:
            EventCancelledError: If a listener cancels the event during
                propagation and the emitter is configured to raise on cancel.

        Example:
            >>> result = event("hello", target="world")
            >>> result["listeners_executed"]
            1
        """
        ...
