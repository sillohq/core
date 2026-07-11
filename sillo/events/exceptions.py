class EventError(Exception):
    """Base exception for event-related errors"""

    pass


class ListenerAlreadyRegisteredError(EventError):
    """Raised when a listener is already registered"""

    pass


class MaxListenersExceededError(EventError):
    """Raised when maximum number of listeners is exceeded"""

    pass


class EventCancelledError(EventError):
    """Raised when an event is cancelled"""

    pass
