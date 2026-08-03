"""Database and migration operations, as functions.

sillo deliberately ships no command-line interface. Building one means choosing
an argument parser, an output format and a set of names, and those are the
application's decisions — or its tooling's. What the framework owes you is the
operations themselves, callable from anywhere.

``sillo-start`` builds its CLI on these. So can a Click group of your own, a
management script, or a test.

Usage::

    from sillo.record import DatabaseConfig, DatabaseManager
    from sillo.record.commands import make, migrate

    database = DatabaseManager(DatabaseConfig(url=...))
    database.register_models("database.models").set_migrations("database.migrations")

    await make(database, "add_posts")
    await migrate(database)
"""

from __future__ import annotations

from .functions import init, make, migrate, plan, rollback, sql

__all__ = [
    "init",
    "make",
    "migrate",
    "plan",
    "rollback",
    "sql",
]
