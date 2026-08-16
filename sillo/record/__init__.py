"""sillo.record — Eloquent-level database toolkit wrapping Tortoise ORM."""

from .casting import HasCasts
from .collection import Collection
from .commands import init as init_migrations
from .commands import make as make_migration
from .commands import migrate, plan

# Aliased for the same reason `init` and `make` are: the name collides with
# something else this package exports. `rollback` is the transaction helper
# below -- `begin`/`commit`/`rollback` is one trio and splitting it would be
# the surprising choice -- so the migration command takes the suffixed name.
#
# Unaliased, the two `rollback` imports both bound the bare name and the
# second won, so `from sillo.record import rollback` silently handed back
# `rollback(connection_name="default")`. Calling it the documented way,
# `rollback(database, target)`, then failed with "takes from 0 to 1
# positional arguments but 2 were given" -- an arity error about a function
# the caller never asked for.
from .commands import rollback as rollback_migrations
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
    "rollback_migrations",
    "setup_record",
    "transaction",
]
