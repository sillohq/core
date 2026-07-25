"""
sillo.record.casting — Attribute casting (like Laravel's $casts).

Define a ``_casts`` dict on your model to automatically cast attributes
when reading from or writing to the database.

Supported cast types:
- ``"json"`` — encode/decode JSON
- ``"datetime"`` — parse/format ISO datetime strings
- ``"bool"`` — convert to Python bool
- ``"int"`` / ``"float"`` — numeric casting
- ``"encrypted"`` — encrypt/decrypt with the provided key
- Any callable that returns ``(encoder, decoder)``
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any, Callable, Dict, Optional


class CastRegistry:
    """Registry of named casters."""

    _builtins: Dict[str, tuple[Callable, Callable]] = {}

    @classmethod
    def register(cls, name: str, encoder: Callable, decoder: Callable) -> None:
        """Register

        Args:
            name: [description]
            encoder: [description]
            decoder: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        cls._builtins[name] = (encoder, decoder)

    @classmethod
    def get(cls, name: str):
        """Get

        Args:
            name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return cls._builtins.get(name)


def _json_encoder(value: Any) -> str:
    """Json Encoder

    Args:
        value: [description]

    Returns:
        [description]

    Raises:
        [description]
    """
    return json.dumps(value, default=str)


def _json_decoder(value: str) -> Any:
    """Json Decoder

    Args:
        value: [description]

    Returns:
        [description]

    Raises:
        [description]
    """
    return json.loads(value) if isinstance(value, str) else value


def _datetime_encoder(value: datetime) -> str:
    """Datetime Encoder

    Args:
        value: [description]

    Returns:
        [description]

    Raises:
        [description]
    """
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _datetime_decoder(value: str) -> Optional[datetime]:
    """Datetime Decoder

    Args:
        value: [description]

    Returns:
        [description]

    Raises:
        [description]
    """
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _encrypted_factory(key: str):
    """Create an encrypted caster with a symmetric key."""

    def encoder(value: str) -> str:
        """Encoder

        Args:
            value: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        # Simple XOR + base64 for demo. Use cryptography.fernet in production.
        encoded = bytes([ord(c) ^ ord(key[i % len(key)]) for i, c in enumerate(value)])
        return base64.b64encode(encoded).decode()

    def decoder(value: str) -> str:
        """Decoder

        Args:
            value: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        decoded = base64.b64decode(value)
        return "".join(chr(b ^ ord(key[i % len(key)])) for i, b in enumerate(decoded))

    return encoder, decoder


CastRegistry.register("json", _json_encoder, _json_decoder)
CastRegistry.register("datetime", _datetime_encoder, _datetime_decoder)
CastRegistry.register("bool", lambda v: bool(v), lambda v: bool(v))
CastRegistry.register(
    "int", lambda v: int(v), lambda v: int(v) if v is not None else None
)
CastRegistry.register(
    "float", lambda v: float(v), lambda v: float(v) if v is not None else None
)


class HasCasts:
    """Mixin that adds attribute casting to a model.

    Define ``_casts`` on your model::

        class User(Model, HasCasts):
            _casts = {
                "metadata": "json",
                "last_login": "datetime",
                "is_admin": "bool",
                "secret_key": ("encrypted", {"key": "my-secret"}),
            }
    """

    _casts: Dict[str, Any] = {}

    def get_cast(self, field_name: str):
        """Get Cast

        Args:
            field_name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        cast_def = self._casts.get(field_name)
        if cast_def is None:
            return None, None
        if isinstance(cast_def, str):
            return CastRegistry.get(cast_def) or (None, None)
        if isinstance(cast_def, tuple):
            name, kwargs = cast_def[0], cast_def[1] if len(cast_def) > 1 else {}
            if name == "encrypted":
                return _encrypted_factory(**kwargs)
        if callable(cast_def):
            return cast_def()
        return None, None

    def cast_get(self, field_name: str, value: Any) -> Any:
        """Cast Get

        Args:
            field_name: [description]
            value: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        _, decoder = self.get_cast(field_name)
        if decoder and value is not None:
            return decoder(value)
        return value

    def cast_set(self, field_name: str, value: Any) -> Any:
        """Cast Set

        Args:
            field_name: [description]
            value: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        encoder, _ = self.get_cast(field_name)
        if encoder and value is not None:
            return encoder(value)
        return value
