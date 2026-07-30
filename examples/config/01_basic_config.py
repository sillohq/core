"""Basic configuration example.

Run with:
    uv run python examples/config/01_basic_config.py
"""

from sillo.config import Config, Field
from typing import Literal


class AppConfig(Config):
    """Application configuration loaded from .env"""

    # Required fields (no default)
    database_url: str
    jwt_secret: str

    # Optional fields with defaults
    debug: bool = False
    log_level: Literal['debug', 'info', 'warning', 'error'] = 'info'
    port: int = 8000
    host: str = '127.0.0.1'

    class Config:
        env_file = '.env'
        case_sensitive = False


def main():
    """Demonstrate basic config usage."""

    # Load config from .env
    config = AppConfig()

    print("Configuration loaded successfully!")
    print()
    print(f"Database: {config.database_url}")
    print(f"Debug Mode: {config.debug}")
    print(f"Log Level: {config.log_level}")
    print(f"Server: {config.host}:{config.port}")
    print(f"JWT Secret: {'***' if config.jwt_secret else 'NOT SET'}")
    print()
    print("Full config:")
    print(config)
    print()

    # Type hints work!
    # These are all properly typed:
    db: str = config.database_url
    is_debug: bool = config.debug
    level: Literal['debug', 'info', 'warning', 'error'] = config.log_level
    port: int = config.port

    print("All fields have proper type hints!")
    print(f"- database_url: {type(db).__name__}")
    print(f"- debug: {type(is_debug).__name__}")
    print(f"- log_level: {type(level).__name__}")
    print(f"- port: {type(port).__name__}")


if __name__ == "__main__":
    main()
