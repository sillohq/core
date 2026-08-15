"""
sillo.record.casting — Attribute casting (like Laravel's $casts).

Define a ``_casts`` dict on your model to automatically cast attributes
when reading from or writing to the database.

Supported cast types:
- ``"json"`` — encode/decode JSON
- ``"datetime"`` — parse/format ISO datetime strings
- ``"bool"`` — convert to Python bool
- ``"int"`` / ``"float"`` — numeric casting
- ``"encrypted"`` — Fernet encrypt/decrypt, keyed by the provided passphrase
  (needs the optional ``cryptography`` package)
- Any callable that returns ``(encoder, decoder)``
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, ClassVar


class CastRegistry:
    """Registry of named casters."""

    _builtins: ClassVar[dict[str, tuple[Callable, Callable]]] = {}

    @classmethod
    def register(cls, name: str, encoder: Callable, decoder: Callable) -> None:
        """Register"""
        cls._builtins[name] = (encoder, decoder)

    @classmethod
    def get(cls, name: str):
        """Get"""
        return cls._builtins.get(name)


def _json_encoder(value: Any) -> str:
    """Json Encoder"""
    return json.dumps(value, default=str)


def _json_decoder(value: str) -> Any:
    """Json Decoder"""
    return json.loads(value) if isinstance(value, str) else value


def _datetime_encoder(value: datetime) -> str:
    """Datetime Encoder"""
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _datetime_decoder(value: str) -> datetime | None:
    """Datetime Decoder"""
    if value is None:
        return None
    return datetime.fromisoformat(value)


#: Fixed salt for the passphrase-to-key derivation below. Field encryption has
#: to be deterministic about its key, so the salt cannot be random per value the
#: way it would be for a password hash. Fernet still generates a fresh IV per
#: encryption, so two writes of the same plaintext do not produce the same
#: ciphertext.
_CAST_KEY_SALT = b"sillo.record.casting/encrypted/v1"


def _fernet_key(passphrase: str) -> bytes:
    """Turn an arbitrary passphrase into a Fernet key."""
    from sillo.helpers.crypto import derive_key

    derived, _ = derive_key(passphrase, salt=_CAST_KEY_SALT)
    return base64.urlsafe_b64encode(derived)


def _encrypted_factory(key: str):
    """Create an encrypted caster with a symmetric key.

    This used to be XOR against a repeating key, which is trivially reversible
    and gave a field named ``encrypted`` no confidentiality at all. It is now
    Fernet (AES-128-CBC with an HMAC-SHA256 tag), keyed by PBKDF2-HMAC-SHA256
    over the passphrase.

    ``cryptography`` is an optional dependency, and its absence raises rather
    than falling back to something weaker: a cast that silently stops
    protecting the column is worse than one that refuses to run.

    Values written by the old caster cannot be read by this one. Anything
    already stored under it was not protected in the first place and needs
    rewriting from plaintext.
    """
    from sillo.helpers.crypto import decrypt, encrypt

    fernet_key = _fernet_key(key)

    def encoder(value: str) -> str:
        """Encoder"""
        return encrypt(value, fernet_key)

    def decoder(value: str) -> str:
        """Decoder"""
        return decrypt(value, fernet_key)

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

    _casts: ClassVar[dict[str, Any]] = {}

    def get_cast(self, field_name: str):
        """Get Cast"""
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
        """Cast Get"""
        _, decoder = self.get_cast(field_name)
        if decoder and value is not None:
            return decoder(value)
        return value

    def cast_set(self, field_name: str, value: Any) -> Any:
        """Cast Set"""
        encoder, _ = self.get_cast(field_name)
        if encoder and value is not None:
            return encoder(value)
        return value
