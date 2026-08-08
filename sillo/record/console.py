"""
sillo.record.console — the migration operations, as console commands.

``sillo.record.commands`` supplies the operations as plain functions. This binds
them to a database and gives them names, arguments and output.

Most projects never call this. The ``sillo`` command registers these itself when
the application has a database — :func:`~sillo.record.manager.setup_record` puts
one on ``app.state`` — so the whole migration workflow follows from setup a
project was writing anyway. Call it directly to build a console of your own::

    from sillo.console import Console
    from sillo.record.console import record_commands

    console = Console(prog="python tools.py")
    console.add_many(record_commands(database))

``database`` is either a :class:`~sillo.record.manager.DatabaseManager` or a
callable returning one — a project may export a factory rather than an instance,
so both are accepted rather than making the caller remember which.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar, Union

from sillo.console import Argument, Command, Flag, Option

__all__ = ["record_commands"]


DatabaseSource = Union[Any, Callable[[], Any]]


class _Config:
    """What the migration commands were bound to.

    Args:
        database: The database, or a callable returning one.
        app: The app label whose migrations are managed.
    """

    def __init__(self, database: DatabaseSource, app: str) -> None:
        self.database = database
        self.app = app

    def resolve(self) -> Any:
        """Return the database to act on.

        Returns:
            The bound database. A callable is called on each access rather than
            once at registration, because a factory usually builds a fresh
            manager per invocation and caching it here would share one
            connection across commands that expect their own.
        """
        return self.database() if callable(self.database) else self.database


class RecordCommand(Command):
    """Base for the migration commands.

    Attributes:
        config: Set by :func:`record_commands` on a subclass. Reading it on the
            unbound class is a programming error and says so.
    """

    config: ClassVar[_Config | None] = None

    @property
    def database(self) -> Any:
        """The database this command acts on.

        Returns:
            The bound database.

        Raises:
            RuntimeError: If the command was registered directly instead of
                through :func:`record_commands`.
        """
        if self.config is None:
            raise RuntimeError(
                f"{type(self).__name__} has no database. Register it with "
                f"record_commands(database) rather than adding the class "
                f"directly."
            )
        return self.config.resolve()

    @property
    def app(self) -> str:
        """The app label whose migrations are managed.

        Returns:
            The label, defaulting to ``models``.
        """
        return self.config.app if self.config else "models"

    @staticmethod
    def entries(lines: list[str]) -> list[str]:
        """Keep only the lines of a plan that name a migration.

        ``plan()`` returns display lines, not names: a connection header comes
        back alongside the migrations themselves. Counting the raw list reports
        one migration too many, so the header is dropped here rather than at
        each of the three call sites.

        Args:
            lines: What plan() returned.

        Returns:
            Just the migration lines.
        """
        return [
            line for line in lines if line.strip() and not line.lstrip().startswith("#")
        ]

    @staticmethod
    def counted(number: int) -> str:
        """Describe *number* migrations, with the right plural.

        Args:
            number: How many.

        Returns:
            The phrase, e.g. ``1 migration`` or ``3 migrations``.
        """
        return f"{number} migration" if number == 1 else f"{number} migrations"


class Init(RecordCommand):
    """Create the migration package.

    Safe to re-run. Writes an empty package where migrations are recorded;
    ``db:make`` fills it.
    """

    name = "db:init"
    help = "Create the migration package"

    async def handle(self) -> None:
        from .commands import init

        await init(self.database, app=self.app)
        self.success("Migration package ready.")


class Make(RecordCommand):
    """Write a migration describing the current model changes.

    Writes nothing when the models already match the last migration.
    """

    name = "db:make"
    help = "Write a migration from the current model changes"

    arguments: ClassVar[list] = [
        Argument("name", default=None, help="Suffix for the migration file"),
        Flag("apply", help="Apply it straight away"),
    ]

    async def handle(self) -> None:
        from .commands import make, migrate, plan

        # make() writes nothing when the models already match the last
        # migration, and says so only through the engine's own stdout. Without
        # comparing, this command reports "Migration written" either way — a
        # success message for a file that does not exist.
        before = self.entries(await plan(self.database, app=self.app))
        await make(self.database, self.argument("name"), app=self.app)
        after = self.entries(await plan(self.database, app=self.app))

        if len(after) == len(before):
            self.muted("No model changes to record.")
            return

        if not self.flag("apply"):
            self.success("Migration written.")
            self.muted(f"  Review it, then: {self._migrate_hint()}")
            return

        await migrate(self.database, app=self.app)
        self.success("Migration written and applied.")

    def _migrate_hint(self) -> str:
        """The command line that would apply what was just written.

        Returns:
            The suggestion, using the console's own program name so it is
            copyable rather than approximate.
        """
        prog = self.console.prog if self.console else "sillo"
        return f"{prog} db:migrate"


class Migrate(RecordCommand):
    """Apply every pending migration.

    ``--fake`` adopts a schema that already exists — tables created before the
    project had migrations — by recording them without re-running the DDL.
    """

    name = "db:migrate"
    help = "Apply every pending migration"

    arguments: ClassVar[list] = [
        Option("target", help="Stop at this migration"),
        Flag("fake", help="Record as applied without running the SQL"),
    ]

    async def handle(self) -> None:
        from .commands import migrate, plan

        pending = self.entries(
            await plan(self.database, target=self.option("target"), app=self.app)
        )
        if not pending:
            self.muted("Nothing pending.")
            return

        for line in pending:
            self.bullet(line)
        self.blank()

        await migrate(
            self.database,
            target=self.option("target"),
            fake=self.flag("fake"),
            app=self.app,
        )

        if self.flag("fake"):
            self.success(f"Recorded {self.counted(len(pending))} without running.")
        else:
            self.success(f"Applied {self.counted(len(pending))}.")


class Plan(RecordCommand):
    """Show which migrations would run, without running them."""

    name = "db:plan"
    help = "Show which migrations would run"

    arguments: ClassVar[list] = [Option("target", help="Plan as far as this migration")]

    async def handle(self) -> None:
        from .commands import plan

        pending = self.entries(
            await plan(self.database, target=self.option("target"), app=self.app)
        )
        if not pending:
            self.muted("Nothing pending.")
            return

        self.line(f"{self.counted(len(pending))} pending:")
        for line in pending:
            self.bullet(line)


class Rollback(RecordCommand):
    """Roll the database back to a migration.

    There is no implicit "one step back": name the migration to stop at, or
    ``zero`` to unapply everything.
    """

    name = "db:rollback"
    help = "Roll the database back to a migration"

    arguments: ClassVar[list] = [
        Argument("target", help="Migration to stop at, or 'zero'"),
        Flag("fake", help="Record the rollback without running it"),
        Flag("force", short="f", help="Skip the confirmation"),
    ]

    async def handle(self) -> int | None:
        from .commands import rollback

        target = self.argument("target")

        # Rolling back to zero drops every table. A y/n is too easy to answer
        # by reflex for something with no undo.
        if target == "zero" and not self.flag("force"):
            agreed = self.prompt.confirm_destructive(
                "This unapplies every migration and drops the tables they made.",
                "zero",
            )
            if not agreed:
                self.muted("Nothing done.")
                return 1

        await rollback(self.database, target, fake=self.flag("fake"), app=self.app)
        self.success(f"Rolled back to {target}.")
        return None


class Sql(RecordCommand):
    """Show the SQL a migration would execute, without executing it."""

    name = "db:sql"
    help = "Show the SQL a migration would run"

    arguments: ClassVar[list] = [
        Argument("migration", help="Migration name, e.g. '0001_initial'"),
        Flag("backward", help="Show the rollback SQL instead"),
    ]

    async def handle(self) -> None:
        from .commands import sql

        statements = await sql(
            self.database,
            self.argument("migration"),
            backward=self.flag("backward"),
            app=self.app,
        )
        if not statements:
            self.muted("That migration runs no SQL.")
            return

        for statement in statements:
            self.line(statement)


class Status(RecordCommand):
    """Show whether the database is up to date."""

    name = "db:status"
    help = "Show whether the database is up to date"

    async def handle(self) -> None:
        from .commands import plan

        pending = self.entries(await plan(self.database, app=self.app))

        self.pairs(
            [
                ("app", self.app),
                ("pending", len(pending)),
            ]
        )
        self.blank()

        if not pending:
            self.success("Up to date.")
            return

        self.warn(f"{self.counted(len(pending))} not applied:")
        for line in pending:
            self.bullet(line)


#: Every command this module defines, in the order they are listed.
COMMANDS: list[type[RecordCommand]] = [
    Init,
    Make,
    Migrate,
    Plan,
    Rollback,
    Sql,
    Status,
]


def record_commands(
    database: DatabaseSource,
    *,
    app: str = "models",
    only: list[str] | None = None,
) -> list[type[Command]]:
    """Return the migration commands, bound to *database*.

    Args:
        database: The database to act on, or a callable returning one.
        app: The app label whose migrations are managed.
        only: Names to include, such as ``["db:migrate", "db:make"]``. Omit it
            for all of them.

    Returns:
        Command classes ready to pass to :meth:`~sillo.console.Console.add_many`.

    Raises:
        ValueError: If *only* names a command this module does not define.
    """
    config = _Config(database, app)
    chosen = COMMANDS

    if only is not None:
        available = {command.name: command for command in COMMANDS}
        unknown = [name for name in only if name not in available]
        if unknown:
            raise ValueError(
                f"record_commands has no {unknown[0]!r}. "
                f"It defines: {', '.join(sorted(available))}"
            )
        chosen = [available[name] for name in only]

    # A subclass per registration, so two consoles can bind the same command to
    # different databases without the second overwriting the first.
    return [
        type(command.__name__, (command,), {"config": config}) for command in chosen
    ]
