"""
sillo.record.config — Database configuration with env loading, URL builders,
and backend auto-detection.

Provides fluent factory methods for common database setups and automatic
environment-variable loading so you rarely need to write a connection
string by hand.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any, Dict, Optional

from typing_extensions import Doc


class DatabaseBackend(Enum):
    """Databasebackend

        Returns:
            [description]

        Raises:
            [description]
    """
    SQLITE = "sqlite"
    POSTGRES = "postgres"
    MYSQL = "mysql"
    MARIADB = "mariadb"


@dataclass
class DatabaseConfig:
    """Complete database connection configuration.

    Every field can be read from an environment variable so
    you can keep secrets out of your codebase.

    Usage::

        config = DatabaseConfig.from_env()
        config = DatabaseConfig.postgres("myapp", "s3cret", host="db.internal")
        config = DatabaseConfig.sqlite("data/myapp.db")
    """

    url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite://:memory:")
    )
    backend: DatabaseBackend = DatabaseBackend.SQLITE
    pool_size: int = field(default_factory=lambda: int(os.getenv("DB_POOL_SIZE", "5")))
    max_overflow: int = field(
        default_factory=lambda: int(os.getenv("DB_MAX_OVERFLOW", "10"))
    )
    pool_recycle: int = field(
        default_factory=lambda: int(os.getenv("DB_POOL_RECYCLE", "3600"))
    )
    echo: bool = field(
        default_factory=lambda: os.getenv("DB_ECHO", "false").lower() == "true"
    )
    ssl: bool = field(
        default_factory=lambda: os.getenv("DB_SSL", "false").lower() == "true"
    )
    timezone: str = field(default_factory=lambda: os.getenv("DB_TIMEZONE", "UTC"))
    charset: str = "utf8mb4"
    ssl_ca: Optional[str] = field(default_factory=lambda: os.getenv("DB_SSL_CA"))
    ssl_cert: Optional[str] = field(default_factory=lambda: os.getenv("DB_SSL_CERT"))
    ssl_key: Optional[str] = field(default_factory=lambda: os.getenv("DB_SSL_KEY"))

    def __post_init__(self):
        """Post Init

            Returns:
                [description]

            Raises:
                [description]
        """
        if self.url.startswith("postgres") or self.url.startswith("postgresql"):
            self.backend = DatabaseBackend.POSTGRES
        elif self.url.startswith("mysql"):
            self.backend = DatabaseBackend.MYSQL
        elif self.url.startswith("mariadb"):
            self.backend = DatabaseBackend.MARIADB

    @classmethod
    def from_env(cls, *, prefix: str = "") -> "DatabaseConfig":
        """Create config from environment variables. Uses ``DATABASE_URL`` by default.

        Set *prefix* to load from ``{PREFIX}_DATABASE_URL`` etc.
        """
        if prefix:
            url = os.getenv(f"{prefix}_DATABASE_URL", "sqlite://:memory:")
        else:
            url = os.getenv("DATABASE_URL", "sqlite://:memory:")
        return cls(url=url)

    @classmethod
    def sqlite(
        cls, path: Annotated[str, Doc("File path or ':memory:'.")] = ":memory:"
    ) -> "DatabaseConfig":
        """SQLite connection."""
        return cls(url=f"sqlite://{path}", backend=DatabaseBackend.SQLITE)

    @classmethod
    def postgres(
        cls,
        database: Annotated[str, Doc("Database name.")],
        password: Annotated[str, Doc("Password.")],
        *,
        user: Annotated[str, Doc("Username.")] = "postgres",
        host: Annotated[str, Doc("Host.")] = "localhost",
        port: Annotated[int, Doc("Port.")] = 5432,
    ) -> "DatabaseConfig":
        """PostgreSQL connection."""
        return cls(
            url=f"postgres://{user}:{password}@{host}:{port}/{database}",
            backend=DatabaseBackend.POSTGRES,
        )

    @classmethod
    def mysql(
        cls,
        database: Annotated[str, Doc("Database name.")],
        password: Annotated[str, Doc("Password.")],
        *,
        user: Annotated[str, Doc("Username.")] = "root",
        host: Annotated[str, Doc("Host.")] = "localhost",
        port: Annotated[int, Doc("Port.")] = 3306,
    ) -> "DatabaseConfig":
        """MySQL / MariaDB connection."""
        backend = (
            DatabaseBackend.MARIADB
            if "mariadb" in host.lower()
            else DatabaseBackend.MYSQL
        )
        return cls(
            url=f"mysql://{user}:{password}@{host}:{port}/{database}",
            backend=backend,
        )

    def to_dict(self) -> Dict[str, Any]:
        """To Dict

            Returns:
                [description]

            Raises:
                [description]
        """
        d = {k: v for k, v in self.__dict__.items()}
        d["backend"] = self.backend.value
        return d
