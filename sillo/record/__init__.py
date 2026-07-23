"""sillo.record — Eloquent-level database toolkit wrapping Tortoise ORM."""

from .casting import HasCasts
from .collection import Collection
from .commands import RecordCLI
from .config import DatabaseBackend, DatabaseConfig
from .events import HasEvents, ModelObserver
from .exceptions import register_db_exception_handlers
from .factories import Factory, FactoryBuilder
from .fields import (
    CreatedAtField,
    SlugField,
    SoftDeleteField,
    ULIDField,
    UpdatedAtField,
)
from .helpers import FixtureLoader, MigrationHelper, Seeder
from .logging import QueryLogEntry, QueryLogger
from .manager import DatabaseManager, setup_record
from .mixins import (
    CascadesDeletesMixin,
    HasUlidMixin,
    SerializesToDictMixin,
    SoftDeletesMixin,
    TimestampsMixin,
    ValidatesBeforeSaveMixin,
)
from .models import Model
from .pagination import TortoiseDataHandler, SyncTortoiseDataHandler
from .pydantic import pydantic_model_from_tortoise
from .queries import PaginatedResult, count_by, explain, find_by_ids, iter_all, paginate
from .scopes import HasScopes, RecordManager, RecordQuerySet, ScopeRegistry
from .transactions import TransactionContext, begin, commit, rollback, transaction

__all__ = [
    "Model",
    "DatabaseConfig",
    "DatabaseBackend",
    "DatabaseManager",
    "setup_record",
    "CreatedAtField",
    "UpdatedAtField",
    "SoftDeleteField",
    "SlugField",
    "ULIDField",
    "SoftDeletesMixin",
    "TimestampsMixin",
    "HasUlidMixin",
    "SerializesToDictMixin",
    "ValidatesBeforeSaveMixin",
    "CascadesDeletesMixin",
    "HasScopes",
    "RecordManager",
    "RecordQuerySet",
    "ScopeRegistry",
    "HasEvents",
    "ModelObserver",
    "HasCasts",
    "Collection",
    "PaginatedResult",
    "paginate",
    "iter_all",
    "explain",
    "find_by_ids",
    "count_by",
    "transaction",
    "TransactionContext",
    "begin",
    "commit",
    "rollback",
    "Factory",
    "FactoryBuilder",
    "TortoiseDataHandler",
    "SyncTortoiseDataHandler",
    "QueryLogger",
    "QueryLogEntry",
    "pydantic_model_from_tortoise",
    "register_db_exception_handlers",
    "Seeder",
    "FixtureLoader",
    "MigrationHelper",
    "RecordCLI",
]
