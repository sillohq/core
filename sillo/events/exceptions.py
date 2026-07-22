class EventError(Exception):
    """Base exception for all event-related errors in the sillo events subsystem.

    This class serves as the root of the event exception hierarchy.  Every
    custom exception raised by the event emitter, transport layer, or listener
    registry inherits from ``EventError``, allowing callers to catch the entire
    family with a single ``except EventError`` clause.

    The exception carries the standard :class:`Exception` message and optional
    ``args`` tuple.  Subclasses refine the semantics for specific failure modes
    such as duplicate registration, listener-cap overflow, and cancellation.

    Attributes:
        message: A human-readable description of the error condition.
        args: Positional arguments forwarded to the base :class:`Exception`.

    Example:
        >>> try:
        ...     emitter.on("ping")(handler)
        ... except EventError as exc:
        ...     logger.error("Event subsystem failure: %s", exc)
    """

    pass


class ListenerAlreadyRegisteredError(EventError):
    """Raised when a listener is already registered for a given event channel.

    The event emitter enforces a uniqueness constraint on listener registration
    to prevent duplicate delivery.  When a caller attempts to register the same
    callable (by identity or equality, depending on the emitter configuration)
    more than once for the same channel, this exception is raised to signal the
    conflict immediately rather than silently ignoring the duplicate.

    Typical resolution is to guard the registration with a check or to use the
    emitter's ``once`` / ``prepend`` helpers which handle idempotency.

    Attributes:
        message: Description including the channel name and listener identity.
        args: Positional arguments forwarded to :class:`EventError`.

    Example:
        >>> emitter.on("ping")(handler)
        >>> emitter.on("ping")(handler)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        ListenerAlreadyRegisteredError: ...
    """

    pass


class MaxListenersExceededError(EventError):
    """Raised when the maximum number of listeners for a channel is exceeded.

    Each event channel enforces a configurable upper bound on the number of
    concurrent listeners to prevent resource exhaustion from runaway
    registration loops.  When a new listener would push the count past
    ``max_listeners``, this exception is raised and the registration is
    rejected.

    The limit can be raised via ``emitter.set_max_listeners()`` or per-channel
    configuration.  The default is intentionally conservative to surface
    accidental leaks early in development.

    Attributes:
        message: Description including the channel name and current limit.
        args: Positional arguments forwarded to :class:`EventError`.

    Example:
        >>> emitter.set_max_listeners(1)
        >>> emitter.on("ping")(handler_a)
        >>> emitter.on("ping")(handler_b)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        MaxListenersExceededError: ...
    """

    pass


class EventCancelledError(EventError):
    """Raised when an event is cancelled before or during dispatch.

    Event cancellation can be triggered explicitly by a listener calling
    ``event.cancel()`` during the capture or bubble phase, or by the emitter
    when a pre-dispatch guard detects that the event should not propagate.
    This exception signals to the caller that the emit call was short-circuited
    and remaining listeners were not (or will not be) executed.

    Handlers that need to distinguish cancellation from other failures should
    catch this specific subclass rather than the generic :class:`EventError`.

    Attributes:
        message: Description of the cancellation reason or channel.
        args: Positional arguments forwarded to :class:`EventError`.

    Example:
        >>> try:
        ...     emitter.emit("shutdown")
        ... except EventCancelledError:
        ...     logger.info("Shutdown event was cancelled by a listener")
    """

    pass
