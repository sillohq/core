import json
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    TypeVar,
)

# Type for configuration validation functions
T = TypeVar("T")


class MakeConfig:
    """
    A dynamic configuration class that allows nested dictionary access as attributes,
    with optional validation and immutability.

    Attributes:
        _config (dict): Stores configuration data.
        _immutable (bool): If True, prevents modifications.
        _validate (dict): Stores validation rules for keys.

    Example Usage:
        config = MakeConfig({"db": {"host": "localhost"}}, immutable=True)
        print(config.db.host)  # "localhost"
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        defaults: Optional[Dict[str, Any]] = None,
        validate: Optional[Dict[str, Callable[[Any], bool]]] = None,
        immutable: bool = False,
        **kwargs: Any,
    ):
        """
        Initialize the configuration object.

        Args:
            config (dict): Initial configuration.
            defaults (dict, optional): Default values for missing keys.
            validate (dict, optional): Validation rules (e.g., {"port": lambda x: x > 0}).
            immutable (bool, optional): If True, prevents modifications.
        """
        self._config: Dict[str, Any] = {}
        self._immutable: bool = immutable
        self._validate: Dict[str, Callable[[Any], bool]] = validate or {}

        config = config or {}
        # Merge defaults, config dict, and kwargs, kwargs take highest priority
        merged_config = {**(defaults or {}), **config, **kwargs}

        for key, value in merged_config.items():
            if isinstance(value, MakeConfig):
                self._set_config(key, value.to_dict())
            else:
                self._set_config(key, value)

    def _set_config(self, key: str, value: Optional[Any]):
        """Validates and sets a configuration key."""
        if key in self._validate:
            if not self._validate[key](value):
                raise ValueError(f"Invalid value for '{key}': {value}")

        if isinstance(value, dict):
            value = MakeConfig(value, immutable=self._immutable)  # type: ignore

        self._config[key] = value

    def __setattr__(self, name: str, value: Any):
        """Handles attribute assignment while respecting immutability."""
        if name in {"_config", "_immutable", "_validate"}:
            super().__setattr__(name, value)
        elif self._immutable:
            raise AttributeError(f"Cannot modify immutable config: '{name}'")
        else:
            self._set_config(name, value)

    def __getattr__(self, name: str) -> Any:
        """Handles attribute access, returning None if key is missing."""
        return self._config.get(name, None)

    def _get_nested(self, path: str) -> Any:
        """
        Retrieve a value from nested keys, returning None if any part is missing.

        Args:
            path (str): Dot-separated path, e.g., "db.host".

        Returns:
            Any: The value found or None.
        """
        keys = path.split(".")
        current: Any = self
        for key in keys:
            if not isinstance(current, MakeConfig):
                return None
            current = current._config.get(key, None)
        return current

    def __getitem__(self, path: str) -> Any:
        """Allow dictionary-like access via dot-separated keys."""
        return self._get_nested(path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a standard dictionary."""

        def recurse(config: "MakeConfig") -> Dict[str, Any]:
            if isinstance(config, MakeConfig):  # type: ignore
                return {k: recurse(v) for k, v in config._config.items()}
            return config

        return recurse(self)

    def to_json(self) -> str:
        """Convert configuration to a JSON string."""
        return json.dumps(self.to_dict(), indent=4)

    def __repr__(self) -> str:
        return f"MakeConfig({self.to_dict()})"

    def __str__(self) -> str:
        return str(self.to_dict())

    def update(self, data: Dict[str, Any], *, recursive: bool = True) -> None:
        """
        Update the configuration with values from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary of values to update.
            recursive (bool): If True, update nested MakeConfig objects recursively.
        """
        for key, value in data.items():
            if (
                recursive
                and key in self._config
                and isinstance(self._config[key], MakeConfig)
                and isinstance(value, dict)
            ):
                self._config[key].update(value, recursive=True)
            else:
                self._set_config(key, value)
