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
import os
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

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
        """Init

        Args:
            db_manager: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._db = db_manager
        self._records: List[tuple[type, Dict[str, Any]]] = []

    def seed(
        self,
        model: type,
        records: Annotated[
            List[Dict[str, Any]], Doc("List of field dicts for the model.")
        ],
    ) -> "Seeder":
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
            Optional[Dict[str, Any]],
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
        self._models: Dict[str, Any] = dict(models or {})

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

    def _parse(self, path: Path) -> List[Dict[str, Any]]:
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
    """Run migrations programmatically, using Tortoise's native migration engine.

    Tortoise 1.0 ships its own migration system and aerich itself recommends it
    over aerich for that version onwards, so this helper drives
    ``tortoise.migrations`` rather than aerich. State lives in the
    ``tortoise_migrations`` table.

    Every method opens a connection, does its work and closes again, so the
    helper is safe to call from a short-lived script or a management command.

    Usage::

        helper = MigrationHelper("database.config.TORTOISE_ORM")
        await helper.make("add_posts")   # write a migration from model changes
        await helper.upgrade()           # apply everything pending

    The app whose migrations are managed must declare where they live::

        TORTOISE_ORM = {
            "connections": {"default": os.getenv("DATABASE_URL")},
            "apps": {"models": {
                "models": ["database.models"],
                "default_connection": "default",
                "migrations": "database.migrations",   # <- required
            }},
        }

    Without the ``migrations`` key Tortoise treats the app as unmigrated and
    every command reports "no migrations" while doing nothing.

    Args:
        config: A dotted path to the project's Tortoise config
            (``"database.config.TORTOISE_ORM"``), or the mapping itself. Some
            operations need the dotted path — see :meth:`make`.
        app: Which app label inside ``config["apps"]`` to manage. None means
            every configured app.
    """

    def __init__(
        self,
        config: Annotated[
            "Dict[str, Any] | str",
            Doc("Dotted path to the Tortoise config, or the mapping itself."),
        ],
        *,
        app: Annotated[
            Optional[str], Doc("App label to manage. None means all apps.")
        ] = None,
    ) -> None:
        self._config_path = config if isinstance(config, str) else None
        self._config = self._resolve(config)
        self._app = app

    @staticmethod
    def _resolve(config: "Dict[str, Any] | str") -> Dict[str, Any]:
        """Return a config mapping, importing a dotted path if one was given.

        Raises:
            TypeError: If *config* is neither a mapping nor a dotted path.
            ValueError: If a dotted path does not resolve to a mapping.
        """
        if isinstance(config, dict):
            return config
        if not isinstance(config, str):
            raise TypeError(
                "config must be a Tortoise config mapping or a dotted path to one, "
                f"got {type(config).__name__}."
            )

        module_path, _, attribute = config.rpartition(".")
        if not module_path:
            raise ValueError(
                f"'{config}' is not a dotted path. Use something like "
                "'database.config.TORTOISE_ORM'."
            )
        from importlib import import_module

        resolved = getattr(import_module(module_path), attribute)
        if not isinstance(resolved, dict):
            raise ValueError(
                f"'{config}' resolved to {type(resolved).__name__}, expected a dict."
            )
        return resolved

    @property
    def _app_labels(self) -> Optional[List[str]]:
        """The app labels to operate on, or None for all of them."""
        return [self._app] if self._app else None

    def _qualify(self, target: Optional[str]) -> Optional[str]:
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
        """Run a native migration command that has no public API yet.

        ``makemigrations`` and ``init`` only exist behind the CLI, which reads
        the config by dotted path rather than by value.

        Raises:
            RuntimeError: If the helper was built from a mapping instead of a
                dotted path, or the command exits non-zero.
        """
        if self._config_path is None:
            raise RuntimeError(
                f"'{args[0]}' needs the config as a dotted path. Build the helper "
                'with MigrationHelper("database.config.TORTOISE_ORM") instead of '
                "passing the dict."
            )
        from tortoise.cli.cli import run_cli_async

        argv = ["-c", self._config_path, *args]
        if self._app:
            argv.append(self._app)
        try:
            code = await run_cli_async(argv)
        finally:
            await self._close()
        if code != 0:
            raise RuntimeError(f"tortoise {' '.join(args)} failed with exit code {code}.")

    async def init(self) -> None:
        """Create the migration package for each configured app.

        Safe to re-run; existing packages are left alone.
        """
        await self._cli("init")

    async def make(self, name: Optional[str] = None) -> None:
        """Write a migration file describing the current model changes.

        Args:
            name: Suffix for the migration file. Tortoise derives one from the
                detected operations when omitted.
        """
        args = ["makemigrations"]
        if name:
            args += ["--name", name]
        await self._cli(*args)

    async def upgrade(self, target: Optional[str] = None, *, fake: bool = False) -> None:
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

        target = self._qualify(target)

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

    async def plan(self, target: Optional[str] = None) -> List[str]:
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

    async def sql(self, migration: str, *, backward: bool = False) -> List[str]:
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
