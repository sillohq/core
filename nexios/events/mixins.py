import json
from typing import Type

from .types import _T, EventProtocol


class EventSerializationMixin(EventProtocol):
    """
    Mixin for event serialization capabilities.
    """

    def to_json(self) -> str:
        """Serialize event configuration to JSON"""
        return json.dumps(
            {
                "name": self.name,
                "listener_count": self.listener_count,
                "max_listeners": self.max_listeners,
                "enabled": self.enabled,
                "metrics": self.get_metrics(),
            }
        )

    @classmethod
    def from_json(cls: Type[_T], json_str: str) -> _T:  # type:ignore
        """Deserialize event configuration from JSON"""

        # Note: cls needs to be the concrete class (Event)
        data = json.loads(json_str)
        # Assuming __init__ takes name:
        event = cls(data["name"])  # type: ignore
        event.max_listeners = data["max_listeners"]  # type: ignore
        event.enabled = data["enabled"]  # type: ignore
        return event
