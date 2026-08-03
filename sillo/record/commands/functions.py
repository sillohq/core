"""Database and migration operations, as functions.

sillo ships no command-line interface. These are the operations a CLI would
expose, as plain async functions that a project's own tooling — a management
script, a test, ``sillo-start`` — can call directly.

Each takes the database as sillo describes it: a
:class:`~sillo.record.manager.DatabaseManager`, carrying the same settings the
application runs on::

    from sillo.record import DatabaseConfig, DatabaseManager
    from sillo.record.commands import migrate

    database = DatabaseManager(DatabaseConfig(url=...))
    database.register_models("database.models").set_migrations("database.migrations")

    await migrate(database)

There is one definition of how a project connects, and both the application and
its migrations read it. A resolved configuration mapping, or a dotted path to
one, is also accepted for tooling that has only that.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Dict, List, Optional, Union

from typing_extensions import Doc

from ..helpers import MigrationHelper

if TYPE_CHECKING:
    from ..manager import DatabaseManager

#: The database to act on: a manager, a resolved configuration, or a path to one.
Database = Union["DatabaseManager", Dict[str, Any], str]


def _helper(database: Database, app: Optional[str]) -> MigrationHelper:
    """Bind a helper to *database*."""
    return MigrationHelper(database, app=app)


async def init(
    database: Annotated[Database, Doc("The database to act on.")],
    *,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> None:
    """Create the migration package for *app*.

    Safe to re-run. Writes an empty package where migrations will be recorded;
    :func:`make` fills it.
    """
    await _helper(database, app).init()


async def make(
    database: Annotated[Database, Doc("The database to act on.")],
    name: Annotated[Optional[str], Doc("Suffix for the migration file.")] = None,
    *,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> None:
    """Write a migration describing the current model changes.

    Writes nothing when the models already match the last migration.
    """
    await _helper(database, app).make(name)


async def migrate(
    database: Annotated[Database, Doc("The database to act on.")],
    *,
    target: Annotated[Optional[str], Doc("Stop at this migration.")] = None,
    fake: Annotated[bool, Doc("Record as applied without running the SQL.")] = False,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> None:
    """Apply every pending migration.

    ``fake=True`` adopts a schema that already exists — tables created before
    the project had migrations — by recording them without re-running the DDL.
    """
    await _helper(database, app).upgrade(target=target, fake=fake)


async def rollback(
    database: Annotated[Database, Doc("The database to act on.")],
    target: Annotated[str, Doc("Migration to roll back to, or 'zero'.")],
    *,
    fake: Annotated[bool, Doc("Record the rollback without running it.")] = False,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> None:
    """Roll the database back to *target*.

    There is no implicit "one step back": name the migration to stop at, or
    ``"zero"`` to unapply everything.
    """
    await _helper(database, app).downgrade(target, fake=fake)


async def plan(
    database: Annotated[Database, Doc("The database to act on.")],
    *,
    target: Annotated[Optional[str], Doc("Plan as far as this migration.")] = None,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> List[str]:
    """Return the migrations that would run, without running them."""
    return await _helper(database, app).plan(target=target)


async def sql(
    database: Annotated[Database, Doc("The database to act on.")],
    migration: Annotated[str, Doc("Migration name, e.g. '0001_initial'.")],
    *,
    backward: Annotated[bool, Doc("Show the rollback SQL instead.")] = False,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> List[str]:
    """Return the SQL a migration would execute, without executing it."""
    return await _helper(database, app).sql(migration, backward=backward)
