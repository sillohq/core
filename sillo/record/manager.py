"""
sillo.record.manager — Database connection lifecycle for sillo applications.

Handles Tortoise ORM init/shutdown and registers with the app's startup
and shutdown hooks.
"""

from __future__ import annotations

import logging
import ssl
from typing import Annotated, Any

from tortoise import Tortoise, connections
from tortoise.backends.base.config_generator import expand_db_url
from typing_extensions import Doc, Self

from .config import DatabaseConfig

try:
    from tortoise.context import _current_context
except ModuleNotFoundError:
    _current_context = None  # ty: ignore[invalid-assignment]

logger = logging.getLogger("sillo.record")

#: URL schemes sillo accepts that Tortoise's parser does not know by name.
_SCHEME_ALIASES = {
    "postgresql": "postgres",
    "mariadb": "mysql",
}


def _normalize_db_url(url: str) -> str:
    """Rewrite scheme aliases to the names Tortoise's URL parser knows.

    ``postgresql://`` and ``mariadb://`` are both accepted by
    :class:`~sillo.record.config.DatabaseConfig` but rejected by Tortoise,
    which only knows ``postgres``/``asyncpg``/``psycopg`` and ``mysql``.

    Args:
        url: The connection URL as configured.

    Returns:
        The same URL with its scheme rewritten when it is an alias, otherwise
        the URL unchanged.
    """
    scheme, sep, rest = url.partition("://")
    if not sep:
        return url
    return f"{_SCHEME_ALIASES.get(scheme, scheme)}://{rest}"


def _build_ssl_context(cfg: DatabaseConfig) -> ssl.SSLContext:
    """Build the SSL context handed to the database driver.

    Both asyncpg and aiomysql take an :class:`ssl.SSLContext` for their
    ``ssl`` argument. The certificate paths on the config are optional; with
    none of them set this returns the system default context, which still
    verifies the server certificate.

    Args:
        cfg: The database configuration carrying the certificate paths.

    Returns:
        A configured :class:`ssl.SSLContext`.
    """
    context = ssl.create_default_context(cafile=cfg.ssl_ca)
    if cfg.ssl_cert:
        context.load_cert_chain(cfg.ssl_cert, keyfile=cfg.ssl_key)
    return context


class DatabaseManager:
    """Manages Tortoise ORM lifecycle for a sillo application.

    Usage::

        db = DatabaseManager(config)
        await db.init()
        # ... app running ...
        await db.shutdown()
    """

    def __init__(
        self, config: Annotated[DatabaseConfig, Doc("Connection configuration.")]
    ):
        """Init"""
        self.config = config
        self._initialized = False
        self._model_modules: list[str] = []
        self._migrations_module: str = "database.migrations"
        # Set by init(). Named here so ensure_context() can run before the
        # database is up — during a request that arrives while starting.
        self._root_context = None

    def register_models(
        self,
        *modules: Annotated[
            str, Doc("Dotted module paths containing Tortoise models.")
        ],
    ) -> DatabaseManager:
        """Register model modules to be discovered on init.

        Returns the manager, so it chains with :meth:`set_migrations`.
        """
        self._model_modules.extend(modules)
        return self

    def set_migrations(
        self,
        module: Annotated[str, Doc("Dotted path to the migrations package.")],
    ) -> DatabaseManager:
        """Declare where this project's migrations live.

        Defaults to ``database.migrations``. Returns the manager, so it chains
        with :meth:`register_models`.
        """
        self._migrations_module = module
        return self

    async def init(self) -> None:
        """Initialize Tortoise ORM with the configured backend."""
        if self._initialized:
            return
        cfg = self._build_tortoise_config()
        # Tortoise.init() creates a TortoiseContext and enters it in the
        # *startup* task. ASGI request handling runs in a separate task, so the
        # contextvar is not propagated — capture the context here and re-enter
        # it per-request in ensure_context().
        self._root_context = await Tortoise.init(config=cfg)
        # Off in migration-managed projects: see DatabaseConfig.generate_schemas
        # for why running DDL on every startup is the wrong default there.
        if self.config.generate_schemas:
            await Tortoise.generate_schemas(safe=True)

        self._initialized = True
        logger.info("Database connected — backend=%s", self.config.backend.value)

    async def ensure_context(self, request, response, call_next):
        """Per-request middleware hook.

        Tortoise >=0.25 stores DB connections in a task-scoped
        ``TortoiseContext`` (a contextvar) that is not propagated from the ASGI
        startup task to request-handling tasks, so we re-enter the captured
        root context here for the duration of the request. Older Tortoise keeps
        connections in global state, where a pass-through is sufficient.
        """
        ctx = self._root_context
        if ctx is None or not getattr(ctx, "inited", False):
            return await call_next()

        if _current_context is None:
            # Pre-context Tortoise: connections live in global state.
            return await call_next()

        if _current_context.get() is not None:
            return await call_next()

        token = _current_context.set(ctx)
        try:
            return await call_next()
        finally:
            _current_context.reset(token)

    async def shutdown(self) -> None:
        """Close all database connections."""
        if not self._initialized:
            return
        await connections.close_all()
        self._initialized = False
        logger.info("Database connections closed")

    async def health(self) -> bool:
        """Ping the database to verify connectivity."""
        try:
            conn = connections.get("default")
            await conn.execute_query("SELECT 1")
            return True
        except Exception:
            return False

    async def __aenter__(self) -> Self:
        """Open the database for a block of work.

        For scripts and management commands, where the application's startup
        hooks never run::

            async with DatabaseManager(config).register_models("app.models") as db:
                await User.all()

        Closing matters as much as opening: an open connection keeps the event
        loop alive, and a script that finishes its work then hangs at exit is
        usually this.
        """
        await self.init()
        return self

    async def __aexit__(self, *_exc) -> None:
        """Close the database opened by :meth:`__aenter__`."""
        await self.shutdown()

    def orm_config(
        self,
        migrations: Annotated[
            str | None, Doc("Migrations package, overriding set_migrations.")
        ] = None,
    ) -> dict:
        """The resolved configuration this manager runs on.

        The ORM's own configuration format, built from this manager's
        :class:`~sillo.record.config.DatabaseConfig`. You rarely need it —
        :mod:`sillo.record.commands` and :class:`MigrationHelper` both take the
        manager itself, which is the point: one definition of how the project
        connects, shared by the application and its migrations rather than
        written out twice and kept in step by hand.

        Reach for it when something outside sillo wants the mapping.

        Args:
            migrations: Override the migrations package for this call.

        Returns:
            A configuration dict, including the ``migrations`` key the migration
            engine requires.
        """
        if migrations:
            self._migrations_module = migrations
        return self._build_tortoise_config()

    def _build_tortoise_config(self) -> dict:
        """Build the Tortoise config dict for the configured backend.

        The connection URL is expanded by Tortoise's own URL parser, which
        resolves the driver module and splits out host, port, user, password
        and database. sillo's extra options are then layered on top using the
        credential names each driver actually accepts.

        Returns:
            A Tortoise config dict with ``connections``, ``apps`` and
            ``timezone`` keys.

        Raises:
            ConfigurationError: If the URL scheme is not one Tortoise
                recognises.
        """
        cfg = self.config
        modules = self._model_modules or ["__main__"]

        expanded = expand_db_url(_normalize_db_url(cfg.url))
        engine: str = expanded["engine"]
        credentials: dict[str, Any] = dict(expanded["credentials"])

        if engine != "tortoise.backends.sqlite":
            # Both the postgres and mysql clients pop these out of **kwargs.
            credentials["minsize"] = cfg.pool_size
            credentials["maxsize"] = cfg.pool_size + cfg.max_overflow

            if cfg.ssl:
                credentials["ssl"] = _build_ssl_context(cfg)

            if engine == "tortoise.backends.mysql":
                credentials["charset"] = cfg.charset
                # aiomysql.create_pool() takes pool_recycle directly.
                credentials["pool_recycle"] = cfg.pool_recycle
            elif engine in (
                "tortoise.backends.asyncpg",
                "tortoise.backends.psycopg",
            ):
                # asyncpg's equivalent knob, in seconds.
                credentials["max_inactive_connection_lifetime"] = cfg.pool_recycle

        if cfg.echo:
            # Tortoise has no `echo` credential; query logging is a logger.
            logging.getLogger("tortoise.db_client").setLevel(logging.DEBUG)

        return {
            "connections": {
                "default": {
                    "engine": engine,
                    "credentials": credentials,
                }
            },
            "apps": {
                "models": {
                    "models": modules,
                    "default_connection": "default",
                    # Where migrations live. Without it Tortoise treats the app
                    # as unmigrated and every migration command reports "no
                    # migrations" while doing nothing at all.
                    "migrations": self._migrations_module,
                }
            },
            "timezone": cfg.timezone,
        }


def setup_record(
    app,
    config: Annotated[DatabaseConfig, Doc("Database configuration.")],
    *,
    model_modules: Annotated[
        list[str] | None, Doc("List of dotted model module paths.")
    ] = None,
) -> DatabaseManager:
    """Wire database lifecycle into a sillo application.

    Stores the manager in ``app.state["record"]`` and registers
    startup/shutdown hooks.

    Usage::

        from sillo import silloApp
        from sillo.record import setup_record, DatabaseConfig

        app = silloApp()
        db = setup_record(app, DatabaseConfig.sqlite("myapp.db"),
                          model_modules=["myapp.models"])
    """
    if "record" in app.state:
        return app.state["record"]

    manager = DatabaseManager(config)
    if model_modules:
        manager.register_models(*model_modules)
    app.state["record"] = manager
    app.use(manager.ensure_context)
    app.on_startup(manager.init)
    app.on_shutdown(manager.shutdown)
    return manager
