"""Configuration management with Pydantic validation.

Loads settings from .env files with full type safety and validation.

Quick Start:

    from sillo.config import Config, Field
    from typing import Literal

    class AppConfig(Config):
        database_url: str
        debug: bool = False
        log_level: Literal['debug', 'info', 'warning', 'error'] = 'info'
        port: int = 8000

    # Load from .env file
    config = AppConfig()

    # Type-safe access
    app = silloApp(debug=config.debug)
"""

from .core import Config, Field

__all__ = ["Config", "Field"]
