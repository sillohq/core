from enum import Enum, auto


class EventPriority(Enum):
    """Enumeration of priority levels for event listener execution ordering.

    Listeners registered with a higher priority are invoked before those with
    a lower priority.  When two listeners share the same priority level they
    execute in registration (FIFO) order.  The five tiers give application
    code fine-grained control over critical-path handlers (e.g. auth checks)
    versus housekeeping listeners (e.g. logging).

    Attributes:
        HIGHEST: Executed first; reserved for critical interceptors such as
            authentication, rate-limiting, or cancellation guards.
        HIGH: Executed after HIGHEST; suitable for validation or data
            transformation that downstream listeners depend on.
        NORMAL: The default priority assigned when none is specified.
        LOW: Executed after NORMAL; appropriate for non-critical side effects
            such as analytics or audit logging.
        LOWEST: Executed last; intended for cleanup, cache invalidation, or
            other best-effort post-processing tasks.
    """

    HIGHEST = auto()
    HIGH = auto()
    NORMAL = auto()
    LOW = auto()
    LOWEST = auto()


class EventPhase(Enum):
    """Enumeration of event propagation phases in the DOM-style lifecycle.

    Events flow through three distinct phases when parent-child relationships
    are established between :class:`~sillo.events.core.Event` instances.
    Understanding these phases is essential for writing listeners that react
    at the correct point in the propagation chain.

    Attributes:
        CAPTURING: The top-down phase where the event travels from the root
            ancestor toward the target event.  Listeners in this phase can
            intercept or veto the event before it reaches its destination.
        AT_TARGET: The phase in which the event is being processed at the
            target event itself — the event on which ``trigger`` was called.
        BUBBLING: The bottom-up phase where the event travels from the target
            back up through parent events.  Listeners here observe results
            produced by the target and earlier-captured data.
    """

    CAPTURING = auto()
    BUBBLING = auto()
    AT_TARGET = auto()
