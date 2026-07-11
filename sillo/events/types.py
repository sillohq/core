from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypeVar, Union
from weakref import ReferenceType, WeakMethod

from .enums import EventPhase

_T = TypeVar("_T", bound="EventProtocol")


@dataclass
class EventContext:
    """Context information about the event"""

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
    """Protocol for event listeners"""

    name: str  # Note: Protocol attributes don't strictly need values but types
    listener_count: int
    max_listeners: int
    enabled: bool

    def get_metrics(self) -> dict[str, Any]: ...

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...
