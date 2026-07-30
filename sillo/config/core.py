"""Core configuration class using Pydantic."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field as PydanticField


class Config(BaseModel):
    """Base configuration class with .env file support.

    Extends Pydantic's BaseModel to provide:
    - Automatic .env file loading (via python-dotenv)
    - Type validation
    - Environment variable mapping
    - IDE autocomplete
    - Clear required vs optional fields

    Example:

        from sillo.config import Config, Field
        from typing import Literal

        class AppConfig(Config):
            # Required fields
            database_url: str
            jwt_secret: str

            # Optional fields with defaults
            debug: bool = False
            log_level: Literal['debug', 'info', 'warning', 'error'] = 'info'
            port: int = 8000

            class Config:
                env_file = '.env'
                case_sensitive = False

        config = AppConfig()
        print(config.database_url)
        print(config.debug)  # False
    """

    model_config = ConfigDict(
        extra='ignore',
    )

    def __init__(self, _env_file: Optional[str] = None, _case_sensitive: bool = False, **data):
        """Initialize config, loading from .env if configured.

        Parameters:
            _env_file: Path to .env file to load (overrides Config.env_file)
            _case_sensitive: Whether environment variable names are case-sensitive (overrides Config.case_sensitive)
            **data: Configuration values to set
        """
        # Check if subclass has env_file config
        config_dict = getattr(self.__class__.Config, '__dict__', {}) if hasattr(self.__class__, 'Config') else {}
        env_file = _env_file or config_dict.get('env_file')
        case_sensitive = _case_sensitive or config_dict.get('case_sensitive', False)

        # Load .env file if specified
        if env_file:
            from dotenv import load_dotenv
            load_dotenv(env_file)

        # Load from environment variables
        import os
        env_data = {}
        for field_name in self.__class__.model_fields:
            env_key = field_name if case_sensitive else field_name.upper()
            if env_key in os.environ:
                env_data[field_name] = os.environ[env_key]

        # Merge with provided data (provided data takes precedence)
        env_data.update(data)
        super().__init__(**env_data)

    def __repr__(self) -> str:
        """Pretty repr that masks secrets."""
        fields_repr = {}
        for field_name, field_value in self.model_dump().items():
            if self._is_secret_field(field_name):
                fields_repr[field_name] = '***'
            else:
                fields_repr[field_name] = field_value
        return f"<{self.__class__.__name__} {fields_repr}>"

    @staticmethod
    def _is_secret_field(field_name: str) -> bool:
        """Check if field name suggests it contains a secret."""
        secret_keywords = (
            'secret', 'key', 'password', 'token', 'apikey',
            'api_key', 'auth', 'credential', 'private'
        )
        return any(keyword in field_name.lower() for keyword in secret_keywords)


# Re-export Pydantic Field for convenience
Field = PydanticField

__all__ = ["Config", "Field"]
