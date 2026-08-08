"""sillo.record — Eloquent-level database toolkit wrapping Tortoise ORM."""

from .casting import HasCasts
from .collection import Collection
from .commands import init as init_migrations
from .commands import make as make_migration
from .commands import migrate, plan, rollback
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
from .pagination import SyncTortoiseDataHandler, TortoiseDataHandler
from .pydantic import pydantic_model_from_tortoise
from .queries import PaginatedResult, count_by, explain, find_by_ids, iter_all, paginate
from .scopes import HasScopes, RecordManager, RecordQuerySet, ScopeRegistry
from .transactions import TransactionContext, begin, commit, rollback, transaction

__all__ = [
    "CascadesDeletesMixin",
    "Collection",
    "CreatedAtField",
    "DatabaseBackend",
    "DatabaseConfig",
    "DatabaseManager",
    "Factory",
    "FactoryBuilder",
    "FixtureLoader",
    "HasCasts",
    "HasEvents",
    "HasScopes",
    "HasUlidMixin",
    "MigrationHelper",
    "Model",
    "ModelObserver",
    "PaginatedResult",
    "QueryLogEntry",
    "QueryLogger",
    "RecordManager",
    "RecordQuerySet",
    "ScopeRegistry",
    "Seeder",
    "SerializesToDictMixin",
    "SlugField",
    "SoftDeleteField",
    "SoftDeletesMixin",
    "SyncTortoiseDataHandler",
    "TimestampsMixin",
    "TortoiseDataHandler",
    "TransactionContext",
    "ULIDField",
    "UpdatedAtField",
    "ValidatesBeforeSaveMixin",
    "begin",
    "commit",
    "count_by",
    "explain",
    "find_by_ids",
    "init_migrations",
    "iter_all",
    "make_migration",
    "migrate",
    "paginate",
    "plan",
    "pydantic_model_from_tortoise",
    "register_db_exception_handlers",
    "rollback",
    "setup_record",
    "transaction",
]
