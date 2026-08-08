import json

from .types import _T, EventProtocol


class EventSerializationMixin(EventProtocol):
    """Mixin that adds JSON serialization and deserialization to event objects.

    This mixin implements a pair of complementary methods — :meth:`to_json` and
    :meth:`from_json` — that allow an event's configuration and metrics to be
    round-tripped through a JSON string.  The serialized form captures the
    event's name, listener count, max-listener cap, enabled flag, and a
    snapshot of its current metrics.

    The mixin is designed to be composed with any class that satisfies the
    :class:`~sillo.events.types.EventProtocol` structural protocol, so it does
    not impose a specific base class.  Subclasses must ensure the protocol
    attributes (``name``, ``listener_count``, ``max_listeners``, ``enabled``)
    are set before calling :meth:`to_json`.

    Attributes:
        name: The channel name of the event.
        listener_count: Current number of registered listeners.
        max_listeners: Upper bound on the number of listeners allowed.
        enabled: Whether the event is currently active for dispatch.

    Example:
        >>> serialized = event.to_json()
        >>> restored = MyEvent.from_json(serialized)
        >>> restored.name == event.name
        True
    """

    def to_json(self) -> str:
        """Serialize the event's configuration and metrics to a JSON string.

        Produces a self-contained JSON representation of the event's current
        state, suitable for storage, transmission over a wire protocol, or
        debugging introspection.  The output includes the event name, listener
        count, maximum listener cap, enabled flag, and a live snapshot of the
        metrics dictionary returned by :meth:`get_metrics`.

        The resulting string can be passed to :meth:`from_json` to reconstruct
        an equivalent event instance (modulo transient runtime state such as
        registered listener callables, which are not serializable).

        Returns:
            A JSON-encoded string containing the event's configuration fields
            and a metrics snapshot.  The string is guaranteed to be valid UTF-8
            and parseable by :func:`json.loads`.

        Example:
            >>> data = event.to_json()
            >>> import json
            >>> parsed = json.loads(data)
            >>> "name" in parsed and "metrics" in parsed
            True
        """
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
    def from_json(cls: type[_T], json_str: str) -> _T:
        """Deserialize an event instance from a JSON configuration string.

        Parses the JSON string produced by :meth:`to_json` and constructs a new
        instance of *cls* with the captured configuration.  Only the persistent
        fields (``name``, ``max_listeners``, ``enabled``) are restored; the
        listener registry and transient metrics are left at their defaults
        because callable listeners cannot survive JSON round-tripping.

        The caller is responsible for ensuring that *json_str* was produced by
        a compatible :meth:`to_json` call (i.e. it contains the expected keys).
        Malformed input will raise :class:`json.JSONDecodeError` or
        :class:`KeyError`.

        Args:
            json_str: A JSON-encoded string previously produced by
                :meth:`to_json`.  Must contain at least ``"name"``,
                ``"max_listeners"``, and ``"enabled"`` keys.

        Returns:
            A new instance of *cls* initialized with the deserialized
            configuration values.  The instance is fully functional but starts
            with an empty listener registry.

        Raises:
            json.JSONDecodeError: If *json_str* is not valid JSON.
            KeyError: If required keys (``"name"``, ``"max_listeners"``,
                ``"enabled"``) are missing from the parsed data.

        Example:
            >>> restored = MyEvent.from_json(event.to_json())
            >>> restored.max_listeners == event.max_listeners
            True
        """
        data = json.loads(json_str)
        event = cls(data["name"])  # ty: ignore[too-many-positional-arguments]
        event.max_listeners = data["max_listeners"]
        event.enabled = data["enabled"]
        return event
