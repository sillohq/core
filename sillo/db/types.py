"""
sillo.db.types — Shared types and exceptions for the database layer.

Every enum, dataclass, and exception used across the db subsystem.
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Any, Dict, List, Optional


class DatabaseBackend(enum.Enum):
    """Supported database backends."""

    SQLITE = "sqlite"
    POSTGRES = "postgres"
    MYSQL = "mysql"
    MARIADB = "mariadb"


class IndexType(enum.Enum):
    BTREE = "btree"
    HASH = "hash"
    GIN = "gin"
    GIST = "gist"
    FULLTEXT = "fulltext"


class IntegrityAction(enum.Enum):
    CASCADE = "cascade"
    RESTRICT = "restrict"
    SET_NULL = "set null"
    SET_DEFAULT = "set default"
    NO_ACTION = "no action"


class DatabaseError(Exception):
    """Base for all database-related errors."""


class ConnectionError_(DatabaseError):
    """Cannot establish or maintain a database connection."""


class MigrationError(DatabaseError):
    """Migration could not be applied."""


class QueryError(DatabaseError):
    """Query execution failed."""


class ValidationError(DatabaseError):
    """Model validation failed."""


@dataclasses.dataclass
class DatabaseConfig:
    """Complete database configuration."""

    url: str = "sqlite://:memory:"
    backend: DatabaseBackend = DatabaseBackend.SQLITE
    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle: int = 3600
    echo: bool = False
    ssl: bool = False
    ssl_ca: Optional[str] = None
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    timezone: str = "UTC"
    charset: str = "utf8mb4"

    @classmethod
    def from_url(cls, url: str, **kwargs) -> "DatabaseConfig":
        """Create config from a connection URL, auto-detecting the backend."""
        if url.startswith("sqlite"):
            backend = DatabaseBackend.SQLITE
        elif url.startswith("postgres") or url.startswith("postgresql"):
            backend = DatabaseBackend.POSTGRES
        elif url.startswith("mysql"):
            backend = DatabaseBackend.MYSQL
        elif url.startswith("mariadb"):
            backend = DatabaseBackend.MARIADB
        else:
            raise DatabaseError(f"Unknown database URL scheme: {url}")
        return cls(url=url, backend=backend, **kwargs)

    @classmethod
    def sqlite(cls, path: str = ":memory:", **kwargs) -> "DatabaseConfig":
        return cls(url=f"sqlite://{path}", backend=DatabaseBackend.SQLITE, **kwargs)

    @classmethod
    def postgres(cls, user: str, password: str, host: str = "localhost", port: int = 5432, database: str = "postgres", **kwargs) -> "DatabaseConfig":
        return cls(url=f"postgres://{user}:{password}@{host}:{port}/{database}", backend=DatabaseBackend.POSTGRES, **kwargs)

    @classmethod
    def mysql(cls, user: str, password: str, host: str = "localhost", port: int = 3306, database: str = "mysql", **kwargs) -> "DatabaseConfig":
        return cls(url=f"mysql://{user}:{password}@{host}:{port}/{database}", backend=DatabaseBackend.MYSQL, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in dataclasses.asdict(self).items()}
