from __future__ import annotations

import typing
from typing import Any, Dict

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]


class Address(typing.NamedTuple):
    """
    Represents a network address consisting of a host and port pair.

    This named tuple provides a lightweight, immutable container for storing
    TCP/UDP network address information. It is commonly used to represent
    client and server addresses in ASGI connection scopes.

    Attributes:
        host (str): The hostname or IP address string of the network endpoint.
        port (int): The port number of the network endpoint.
    """

    host: str
    port: int


class Secret:
    """
    Holds a string value that should not be revealed in tracebacks, repr output,
    or other debugging contexts.

    This class wraps a string value and ensures that its contents are masked
    when the object is displayed in tracebacks, logging output, or interactive
    consoles. The actual string value can be retrieved by explicitly casting
    the object to ``str``. This is useful for storing sensitive configuration
    values such as API keys, database passwords, and authentication tokens.

    The class supports truthiness testing via ``__bool__``, allowing it to be
    used in conditional expressions to check whether a secret value has been set.
    """

    def __init__(self, value: str):
        """
        Initializes the Secret with the given string value.

        Stores the provided value in an internal attribute that is masked
        from repr and traceback output. The value can be accessed by
        explicitly converting the Secret instance to a string.

        Args:
            value (str): The sensitive string value to store and protect
                from accidental exposure in debugging output.
        """
        self._value = value

    def __repr__(self) -> str:
        """
        Returns a masked string representation of the Secret object.

        Produces a repr string that hides the actual secret value by replacing
        it with asterisks, preventing accidental exposure in debugging output,
        logging, or interactive console sessions.

        Returns:
            str: A string of the form ``Secret('**********')`` with the actual
            value masked by asterisks.
        """
        class_name = self.__class__.__name__
        return f"{class_name}('**********')"

    def __str__(self) -> str:
        """
        Returns the actual secret string value.

        Provides explicit access to the underlying secret value when the
        object is converted to a string. This is the intended mechanism
        for retrieving the secret value at the point where it is needed.

        Returns:
            str: The actual unmasked secret string value.
        """
        return self._value

    def __bool__(self) -> bool:
        """
        Evaluates the truthiness of the secret value.

        Returns True if the underlying secret string is non-empty, and
        False if it is an empty string. This allows Secret objects to be
        used directly in conditional expressions.

        Returns:
            bool: True if the secret value is a non-empty string, False
            if the secret value is an empty string.
        """
        return bool(self._value)


class State:
    """
    An object that can be used to store arbitrary state via attribute access.

    Provides a dictionary-backed container that supports both attribute-style
    and dictionary-style access for storing and retrieving arbitrary data.
    This is used throughout the framework for ``request.state`` and ``app.state``
    to allow middleware and handlers to share data during request processing.

    Attribute access that references a non-existent key returns ``None`` rather
    than raising an ``AttributeError``, making it safe to check for optional
    state values without explicit error handling.
    """

    _state: typing.Dict[str, typing.Any]

    def __init__(self, state: typing.Optional[typing.Dict[str, typing.Any]] = None):
        """
        Initializes the State object with an optional dictionary of initial values.

        Creates the internal state dictionary, either from the provided dictionary
        or as an empty dictionary if no initial state is given. Uses
        ``super().__setattr__`` to bypass the custom ``__setattr__`` method
        during initialization.

        Args:
            state (Optional[Dict[str, Any]]): An optional dictionary of initial
                key-value pairs to populate the state with. Defaults to None,
                which creates an empty state dictionary.
        """
        if state is None:
            state = {}
        super().__setattr__("_state", state)

    def __setattr__(self, key: typing.Any, value: typing.Any) -> None:
        """
        Sets a state value using attribute assignment syntax.

        Stores the given value in the internal state dictionary under the
        specified key, allowing attribute-style assignment like
        ``state.my_key = my_value``.

        Args:
            key (Any): The attribute name to use as the dictionary key.
            value (Any): The value to store associated with the given key.
        """
        self._state[key] = value

    def __getattr__(self, key: typing.Any) -> typing.Any:
        """
        Retrieves a state value using attribute access syntax.

        Looks up the given key in the internal state dictionary and returns
        its value. If the key does not exist, returns ``None`` instead of
        raising an ``AttributeError``, enabling safe optional state access.

        Args:
            key (Any): The attribute name to look up in the state dictionary.

        Returns:
            Any: The value associated with the key, or None if the key
            does not exist in the state dictionary.
        """
        try:
            return self._state[key]
        except KeyError:
            return None

    def __delattr__(self, key: typing.Any) -> None:
        """
        Removes a state value using attribute deletion syntax.

        Deletes the entry for the given key from the internal state dictionary.
        Raises a ``KeyError`` if the key does not exist in the dictionary.

        Args:
            key (Any): The attribute name to remove from the state dictionary.
        """
        del self._state[key]

    def __str__(self) -> str:
        """
        Returns a human-readable string representation of the State object.

        Produces a string showing the internal state dictionary contents
        for debugging and logging purposes.

        Returns:
            str: A string of the form ``<State data={...}>`` containing the
            current state dictionary representation.
        """
        return f"<State data={self._state}>"

    def update(self, values: Dict[str, Any]):
        """
        Bulk-updates the state with multiple key-value pairs from a dictionary.

        Iterates over the provided dictionary and sets each key-value pair
        in the internal state dictionary, overwriting any existing values
        for keys that already exist.

        Args:
            values (Dict[str, Any]): A dictionary of key-value pairs to merge
                into the current state, replacing any existing entries with
                matching keys.
        """
        for key, value in values.items():
            self._state[key] = value
