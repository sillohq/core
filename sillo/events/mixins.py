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
    def from_json(cls: Type[_T], json_str: str) -> _T:
        """Deserialize event configuration from JSON"""
        data = json.loads(json_str)
        event = cls(data["name"])  # ty: ignore[too-many-positional-arguments]
        event.max_listeners = data["max_listeners"]
        event.enabled = data["enabled"]
        return event
