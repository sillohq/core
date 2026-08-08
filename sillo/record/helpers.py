"""
sillo.record.helpers — Database utilities: seeders, fixtures, migration helpers.

Provides tools for creating test data, running seeders, and managing fixtures.

Usage::

    from sillo.record.helpers import Seeder, FixtureLoader

    seeder = Seeder(db)
    seeder.seed(User, [{"name": "Alice", "email": "a@b.com"}, ...])
    await seeder.run()

    loader = FixtureLoader("fixtures/")
    await loader.load_all()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from typing_extensions import Doc


class Seeder:
    """Seed database tables with test data.

    Usage::

        seeder = Seeder(db_manager)
        seeder.seed(User, [{"email": "alice@ex.com", "name": "Alice"}])
        seeder.seed(Post, [{"title": "Hello", "user_id": 1}])
        await seeder.run()
    """

    def __init__(self, db_manager):
        """Init"""
        self._db = db_manager
        self._records: list[tuple[type, dict[str, Any]]] = []

    def seed(
        self,
        model: type,
        records: Annotated[
            list[dict[str, Any]], Doc("List of field dicts for the model.")
        ],
    ) -> Seeder:
        """Register records for a model. Call :meth:`run` to execute."""
        for record in records:
            self._records.append((model, record))
        return self

    async def run(self, *, batch_size: int = 100) -> int:
        """Execute all registered seeds. Returns number of rows created."""
        count = 0
        for model, data in self._records:
            await model.create(**data)  # ty: ignore[unresolved-attribute]
            count += 1
        return count


class FixtureLoader:
    """Load JSON/JSONL fixture files into the database.

    Directory structure::

        fixtures/
          users.json    →  [{"email": "...", ...}, ...]
          posts.jsonl   →  {"email": "..."}\\n{"email": "..."}\\n...
    """

    #: File extensions ``load_all`` will read. Anything else is ignored.
    SUFFIXES = (".json", ".jsonl")

    def __init__(
        self,
        directory: Annotated[str, Doc("Path to fixtures directory.")],
        *,
        models: Annotated[
            dict[str, Any] | None,
            Doc(
                "Explicit fixture-name to model mapping. Names not listed here "
                "are resolved against Tortoise's model registry."
            ),
        ] = None,
    ):
        """Initialize the loader.

        Args:
            directory: Directory containing the fixture files.
            models: Optional mapping of fixture stem to model class, for cases
                where the filename does not match the model name.
        """
        self._dir = Path(directory)
        self._models: dict[str, Any] = dict(models or {})

    async def load_all(self) -> int:
        """Load every fixture file in the directory.

        Files are loaded in sorted order, so a numeric prefix
        (``01_users.json``, ``02_posts.json``) is how you control the order
        when fixtures reference each other. Files whose suffix is not in
        :attr:`SUFFIXES` are skipped.

        Returns:
            The total number of rows inserted.
        """
        count = 0
        for file_path in sorted(self._dir.glob("*")):
            if file_path.suffix not in self.SUFFIXES or not file_path.is_file():
                continue
            count += await self._load_file(file_path)
        return count

    async def load(
        self, name: Annotated[str, Doc("Fixture name without extension.")]
    ) -> int:
        """Load a specific fixture file by name.

        Returns:
            The number of rows inserted.

        Raises:
            FileNotFoundError: If no fixture with that name exists.
        """
        for ext in self.SUFFIXES:
            path = self._dir / f"{name}{ext}"
            if path.exists():
                return await self._load_file(path)
        raise FileNotFoundError(f"Fixture '{name}' not found in {self._dir}")

    async def _load_file(self, path: Path) -> int:
        """Read one fixture file and insert its rows.

        The whole file is inserted inside a transaction, so a row that fails
        validation or violates a constraint leaves the table untouched rather
        than half-populated.

        Args:
            path: The fixture file to read.

        Returns:
            The number of rows inserted.

        Raises:
            LookupError: If the fixture name matches no registered model.
        """
        records = self._parse(path)
        if not records:
            return 0

        model = self._resolve_model(path.stem)

        from tortoise.transactions import in_transaction

        async with in_transaction():
            for record in records:
                await model.create(**record)
        return len(records)

    def _parse(self, path: Path) -> list[dict[str, Any]]:
        """Decode a fixture file into a list of row dicts.

        Args:
            path: The fixture file to read.

        Returns:
            The rows the file describes. A JSON file holding a single object
            is treated as a one-row fixture.
        """
        content = path.read_text()
        if path.suffix == ".jsonl":
            records = [
                json.loads(line) for line in content.splitlines() if line.strip()
            ]
        else:
            records = json.loads(content)
        if not isinstance(records, list):
            records = [records]
        return records

    def _resolve_model(self, name: str) -> Any:
        """Find the model a fixture file belongs to.

        An explicit entry in the ``models`` mapping always wins. Otherwise the
        filename stem is matched against the registered model names, ignoring
        case and a trailing plural — so ``users.json`` finds ``User`` and
        ``categories.jsonl`` finds ``Category``.

        Args:
            name: The fixture filename without its extension.

        Returns:
            The model class to insert into.

        Raises:
            LookupError: If nothing matches, listing what is registered.
        """
        if name in self._models:
            return self._models[name]

        from tortoise import Tortoise

        registry = {
            model_name.lower(): model
            for app_models in Tortoise.apps.values()
            for model_name, model in app_models.items()
        }

        stem = name.lower()
        candidates = [stem]
        if stem.endswith("ies"):
            candidates.append(stem[:-3] + "y")
        if stem.endswith("es"):
            candidates.append(stem[:-2])
        if stem.endswith("s"):
            candidates.append(stem[:-1])

        for candidate in candidates:
            if candidate in registry:
                return registry[candidate]

        known = ", ".join(sorted(registry)) or "none — has Tortoise been initialised?"
        raise LookupError(
            f"Fixture '{name}' matches no registered model. Known models: {known}. "
            f"Pass FixtureLoader(..., models={{'{name}': YourModel}}) to map it explicitly."
        )


class MigrationHelper:
    """Run migrations programmatically, from a sillo database configuration.

    Give it a :class:`~sillo.record.manager.DatabaseManager` — the same object
    the application runs on — and the schema is managed from one definition of
    how this project connects::

        from sillo.record import DatabaseConfig, DatabaseManager, MigrationHelper

        database = DatabaseManager(DatabaseConfig(url=...))
        database.register_models("database.models")
        database.set_migrations("database.migrations")

        helper = MigrationHelper(database)
        await helper.make("add_posts")   # write a migration from model changes
        await helper.upgrade()           # apply everything pending

    Every method opens a connection, does its work and closes again, so the
    helper is safe to call from a short-lived script or a management command.
    Migration state lives in the ``tortoise_migrations`` table.

    The app being managed must declare where its migrations live —
    :meth:`~sillo.record.manager.DatabaseManager.set_migrations` is how, and
    there is a conventional default. Without it the engine treats the app as
    unmigrated and every command reports "no migrations" while doing nothing.

    Args:
        config: A :class:`DatabaseManager`, a resolved configuration mapping, or
            a dotted path to one.
        app: Which app label to manage. None means every configured app.
    """

    def __init__(
        self,
        config: Annotated[
            Any,
            Doc("A DatabaseManager, a config mapping, or a dotted path to one."),
        ],
        *,
        app: Annotated[
            str | None, Doc("App label to manage. None means all apps.")
        ] = None,
    ) -> None:
        # A path is kept when given, only so an existing dotted-path config
        # still resolves through its own module. Nothing requires one any more.
        self._config_path = config if isinstance(config, str) else None
        self._config = self._resolve(config)
        self._app = app

    @staticmethod
    def _resolve(config: Any) -> dict[str, Any]:
        """Return a configuration mapping, whatever form it arrived in.

        Raises:
            TypeError: If *config* is not a manager, a mapping or a dotted path.
            ValueError: If a dotted path does not resolve to a mapping.
        """
        from .manager import DatabaseManager

        if isinstance(config, DatabaseManager):
            return config.orm_config()
        if isinstance(config, dict):
            return config
        if not isinstance(config, str):
            raise TypeError(
                "config must be a DatabaseManager, a configuration mapping, or a "
                f"dotted path to one, got {type(config).__name__}."
            )

        module_path, _, attribute = config.rpartition(".")
        if not module_path:
            raise ValueError(
                f"'{config}' is not a dotted path. Pass a DatabaseManager instead."
            )
        from importlib import import_module

        resolved = getattr(import_module(module_path), attribute)
        if not isinstance(resolved, dict):
            raise ValueError(
                f"'{config}' resolved to {type(resolved).__name__}, expected a dict."
            )
        return resolved

    @property
    def _app_labels(self) -> list[str] | None:
        """The app labels to operate on, or None for all of them."""
        return [self._app] if self._app else None

    def _qualify(self, target: str | None) -> str | None:
        """Prefix a bare migration name with its app label.

        Tortoise addresses migrations as ``app_label.name`` and reports an
        unqualified name as an unknown *app*, which is a confusing way to learn
        that the prefix was missing.
        """
        if not target or "." in target or not self._app:
            return target
        return f"{self._app}.{target}"

    @staticmethod
    async def _close() -> None:
        """Close the connections the migration engine opened.

        Neither the native API nor the CLI tears Tortoise down, and an open
        connection keeps the event loop alive — a script that finishes its
        migration then hangs forever at interpreter shutdown is this, not a
        deadlock in the migration itself.
        """
        from tortoise import Tortoise

        await Tortoise.close_connections()

    async def _cli(self, *args: str) -> None:
        """Run a migration command that the engine exposes no Python API for.

        ``makemigrations`` and ``init`` live only behind the engine's command
        line, which reads its configuration by importing a dotted path. When
        this helper was built from a manager or a mapping there is no such path,
        so :mod:`sillo.record._bridge` provides one — the config is published on
        a module sillo owns and the path to it handed over.

        Raises:
            RuntimeError: If the command exits non-zero.
        """
        from contextlib import nullcontext

        from tortoise.cli.cli import run_cli_async

        from . import _bridge

        if self._config_path is not None:
            source = nullcontext(self._config_path)
        else:
            source = _bridge.published(self._config)

        with source as config_path:
            argv = ["-c", config_path, *args]
            if self._app:
                argv.append(self._app)
            try:
                code = await run_cli_async(argv)
            finally:
                await self._close()

        if code != 0:
            raise RuntimeError(f"{args[0]} failed with exit code {code}.")

    async def init(self) -> None:
        """Create the migration package for each configured app.

        Safe to re-run; existing packages are left alone.
        """
        await self._cli("init")

    async def make(self, name: str | None = None) -> None:
        """Write a migration file describing the current model changes.

        Args:
            name: Suffix for the migration file. Tortoise derives one from the
                detected operations when omitted.
        """
        args = ["makemigrations"]
        if name:
            args += ["--name", name]
        await self._cli(*args)

    async def upgrade(self, target: str | None = None, *, fake: bool = False) -> None:
        """Apply every pending migration.

        Args:
            target: Stop at this migration instead of the latest.
            fake: Record the migrations as applied without running them.
        """
        from tortoise.migrations import api

        try:
            await api.migrate(
                config=self._config,
                app_labels=self._app_labels,
                target=self._qualify(target),
                fake=fake,
                direction="forward",
            )
        finally:
            await self._close()

    async def downgrade(self, target: str, *, fake: bool = False) -> None:
        """Roll the database back to *target*.

        Args:
            target: Migration to roll back to. Either fully qualified
                (``"models.0001_initial"``) or a bare name (``"0001_initial"``)
                when the helper was built with an ``app``. Use ``"zero"`` to
                unapply everything. Tortoise has no implicit "one step back",
                so this is required.
            fake: Record the rollback without running it.
        """
        from tortoise.migrations import api

        # "zero" is this API's word for "unapply everything"; the engine's is
        # "__first__", which it treats as a backward plan including the root
        # migration. Without the translation the documented spelling raises
        # "Unknown migration target models.zero".
        if target == "zero":
            target = "__first__"
        # Qualified either way: the API resolves an unqualified target as an
        # app label, so a bare "__first__" is rejected as an unknown app.
        target = self._qualify(target) or target

        try:
            await api.migrate(
                config=self._config,
                app_labels=self._app_labels,
                target=target,
                fake=fake,
                direction="backward",
            )
        finally:
            await self._close()

    async def plan(self, target: str | None = None) -> list[str]:
        """Return the ordered list of migrations that would run."""
        from tortoise.migrations import api

        try:
            return await api.plan(
                config=self._config,
                app_labels=self._app_labels,
                target=target,
            )
        finally:
            await self._close()

    async def sql(self, migration: str, *, backward: bool = False) -> list[str]:
        """Return the SQL a migration would execute, without running it.

        Raises:
            ValueError: If the helper manages all apps, since the SQL for a
                migration is app-specific.
        """
        if not self._app:
            raise ValueError("sql() needs a single app; build the helper with app=...")
        from tortoise.migrations import api

        try:
            return await api.sqlmigrate(
                config=self._config,
                app_label=self._app,
                migration_name=migration,
                backward=backward,
            )
        finally:
            await self._close()
