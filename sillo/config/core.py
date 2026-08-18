"""Core configuration class using Pydantic."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField

from sillo.env import autoload, load_env

__all__ = ["Config", "Field"]

#: Tells "the subclass said nothing" apart from "the subclass said ``None``",
#: which is how a project turns .env loading off.
_UNSET: Any = object()

#: A field whose name contains one of these is masked in ``repr``.
SECRET_KEYWORDS = (
    "secret",
    "key",
    "password",
    "token",
    "apikey",
    "api_key",
    "auth",
    "credential",
    "private",
)


class Config(BaseModel):
    """Base configuration class, loaded from the environment.

    Extends Pydantic's ``BaseModel`` with:

    - the project's ``.env`` file, read by sillo itself — ``python-dotenv``
      is not a dependency and is not needed
    - environment variables mapped onto fields
    - type validation, and the IDE autocomplete that comes with it
    - secrets masked in ``repr``

    Nothing has to be configured. Constructing a config loads ``.env`` from
    the project (searching upward from the working directory, stopping at the
    project root) if one is there::

        from sillo.config import Config

        class AppConfig(Config):
            # Required: no default, so a missing DATABASE_URL is an error
            # at startup rather than a None at midnight.
            database_url: str
            jwt_secret: str

            # Optional, with defaults
            debug: bool = False
            log_level: Literal['debug', 'info', 'warning', 'error'] = 'info'
            port: int = 8000

        config = AppConfig()
        config.database_url    # str, validated
        config.port            # int, converted from the string in .env

    Values already exported in the real environment win over the file, so a
    deployment's ``DATABASE_URL`` beats a ``.env`` that shipped in the image.
    Values passed to the constructor win over both.

    An inner ``Env`` class adjusts the defaults::

        class DatabaseConfig(Config):
            url: str
            pool_size: int = 10

            class Env:
                env_file = ".env.production"   # None to load no file at all
                env_prefix = "DATABASE_"       # DATABASE_URL, DATABASE_POOL_SIZE
                case_sensitive = False

    An inner class named ``Config`` is read the same way, which is what
    earlier versions documented. Prefer ``Env``: Pydantic uses ``Config`` for
    its own deprecated class-based settings and warns whenever it sees one.

    Set ``SILLO_ENV_FILE`` to point every config at a different file, or to
    the empty string to turn automatic loading off — useful in tests, where
    the environment should be the only source.
    """

    model_config = ConfigDict(
        extra="ignore",
    )

    def __init__(
        self,
        _env_file: str | None = _UNSET,
        _case_sensitive: bool = _UNSET,
        _env_prefix: str = _UNSET,
        **data: Any,
    ):
        """Initialize config, reading the environment and the ``.env`` file.

        Parameters:
            _env_file: The file to load, overriding the inner ``Config``.
                ``None`` loads no file; left out, the project's ``.env`` is
                found and loaded once.
            _case_sensitive: Whether field names map to environment variables
                verbatim rather than uppercased.
            _env_prefix: Prepended to every environment variable name.
            **data: Values that take precedence over the environment.
        """
        options = self._options()

        env_file = (
            _env_file if _env_file is not _UNSET else options.get("env_file", _UNSET)
        )
        case_sensitive = (
            _case_sensitive
            if _case_sensitive is not _UNSET
            else options.get("case_sensitive", False)
        )
        prefix = (
            _env_prefix if _env_prefix is not _UNSET else options.get("env_prefix", "")
        )

        if env_file is _UNSET:
            # Nothing was asked for: find the project's .env, once per process.
            autoload()
        elif env_file is not None:
            load_env(env_file)

        env_data: dict[str, Any] = {}
        for name, field in self.__class__.model_fields.items():
            alias = field.alias if isinstance(field.alias, str) else None
            for candidate in (alias, name):
                if candidate is None:
                    continue
                key = prefix + candidate
                if not case_sensitive:
                    key = key.upper()
                if key in os.environ:
                    # Keyed by alias when there is one, so the value lands
                    # whether or not the model populates by name.
                    env_data[alias or name] = os.environ[key]
                    break

        # Explicit arguments beat anything the environment had to say.
        env_data.update(data)
        super().__init__(**env_data)

    @classmethod
    def _options(cls) -> dict[str, Any]:
        """Read the subclass's inner options class.

        ``Env`` is the one to write. ``Config`` still works — it is what
        earlier versions documented — but Pydantic claims that name for its
        own deprecated class-based settings, so it warns on every model that
        uses it.

        Returns:
            The options declared, or an empty mapping.
        """
        for name in ("Env", "Config"):
            inner = getattr(cls, name, None)
            if inner is None or inner is cls or not isinstance(inner, type):
                continue
            options = {
                key: value
                for key, value in vars(inner).items()
                if not key.startswith("__")
            }
            if options:
                return options
        return {}

    def __repr__(self) -> str:
        """Pretty repr that masks secrets."""
        fields_repr = {}
        for field_name, field_value in self.model_dump().items():
            if self._is_secret_field(field_name):
                fields_repr[field_name] = "***"
            else:
                fields_repr[field_name] = field_value
        return f"<{self.__class__.__name__} {fields_repr}>"

    def __str__(self) -> str:
        """The masked repr.

        Pydantic's ``__str__`` prints every field's value, and ``print(config)``
        calls ``__str__``, not ``__repr__`` — so masking only the repr leaks
        the secrets at the one moment somebody is most likely to look.
        """
        return self.__repr__()

    @staticmethod
    def _is_secret_field(field_name: str) -> bool:
        """Check if field name suggests it contains a secret."""
        return any(keyword in field_name.lower() for keyword in SECRET_KEYWORDS)


# Re-export Pydantic Field for convenience
Field = PydanticField
