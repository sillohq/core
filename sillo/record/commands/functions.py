"""Database and migration operations, as functions.

sillo ships no command-line interface. These are the operations a CLI would
expose, as plain async functions that a project's own tooling — ``sillo-start``,
a management script, a test — can call directly.

Each takes the Tortoise configuration explicitly. ``DatabaseManager`` builds it
from the settings the application already runs on::

    from sillo.record import DatabaseConfig, DatabaseManager
    from sillo.record.commands import migrate

    manager = DatabaseManager(DatabaseConfig(url=...))
    manager.register_models("database.models")
    await migrate(manager.tortoise_config("database.migrations"))

Passing the configuration as a dotted path — ``"app.database.TORTOISE_ORM"`` —
also works, and is required by :func:`init` and :func:`make`, whose underlying
commands can only read it that way.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, Union

from typing_extensions import Doc

from ..helpers import MigrationHelper

#: A Tortoise configuration, or a dotted path to one.
Config = Union[Dict[str, Any], str]


def _helper(config: Config, app: Optional[str]) -> MigrationHelper:
    """Bind a helper to *config*."""
    return MigrationHelper(config, app=app)


async def init(
    config: Annotated[str, Doc("Dotted path to the Tortoise configuration.")],
    *,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> None:
    """Create the migration package for *app*.

    Safe to re-run. Needs *config* as a dotted path: the command that creates a
    migration package reads its configuration by import, not by value.
    """
    await _helper(config, app).init()


async def make(
    config: Annotated[str, Doc("Dotted path to the Tortoise configuration.")],
    name: Annotated[Optional[str], Doc("Suffix for the migration file.")] = None,
    *,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> None:
    """Write a migration describing the current model changes.

    Needs *config* as a dotted path, for the same reason as :func:`init`.
    Writes nothing when the models already match the last migration.
    """
    await _helper(config, app).make(name)


async def migrate(
    config: Annotated[Config, Doc("Tortoise configuration, or a dotted path.")],
    *,
    target: Annotated[Optional[str], Doc("Stop at this migration.")] = None,
    fake: Annotated[bool, Doc("Record as applied without running the SQL.")] = False,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> None:
    """Apply every pending migration.

    ``fake=True`` adopts a schema that already exists — tables created before
    the project had migrations — by recording them without re-running the DDL.
    """
    await _helper(config, app).upgrade(target=target, fake=fake)


async def rollback(
    config: Annotated[Config, Doc("Tortoise configuration, or a dotted path.")],
    target: Annotated[str, Doc("Migration to roll back to, or 'zero'.")],
    *,
    fake: Annotated[bool, Doc("Record the rollback without running it.")] = False,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> None:
    """Roll the database back to *target*.

    There is no implicit "one step back": name the migration to stop at, or
    ``"zero"`` to unapply everything.
    """
    await _helper(config, app).downgrade(target, fake=fake)


async def plan(
    config: Annotated[Config, Doc("Tortoise configuration, or a dotted path.")],
    *,
    target: Annotated[Optional[str], Doc("Plan as far as this migration.")] = None,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> List[str]:
    """Return the migrations that would run, without running them."""
    return await _helper(config, app).plan(target=target)


async def sql(
    config: Annotated[Config, Doc("Tortoise configuration, or a dotted path.")],
    migration: Annotated[str, Doc("Migration name, e.g. '0001_initial'.")],
    *,
    backward: Annotated[bool, Doc("Show the rollback SQL instead.")] = False,
    app: Annotated[str, Doc("App label to manage.")] = "models",
) -> List[str]:
    """Return the SQL a migration would execute, without executing it."""
    return await _helper(config, app).sql(migration, backward=backward)
