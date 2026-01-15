from enum import Enum, auto


class EventPriority(Enum):
    """Priority levels for event listeners"""

    HIGHEST = auto()
    HIGH = auto()
    NORMAL = auto()
    LOW = auto()
    LOWEST = auto()


class EventPhase(Enum):
    """Event propagation phases"""

    CAPTURING = auto()
    BUBBLING = auto()
    AT_TARGET = auto()
