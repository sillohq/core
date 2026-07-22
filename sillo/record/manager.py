"""
sillo.record.manager — Database connection lifecycle for sillo applications.

Handles Tortoise ORM init/shutdown and registers with the app's startup
and shutdown hooks.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Dict, List, Optional

from tortoise import Tortoise, connections
from typing_extensions import Doc

from .config import DatabaseConfig

try:
    from tortoise.context import _current_context
except ModuleNotFoundError:
    _current_context = None  # type: ignore[assignment]

logger = logging.getLogger("sillo.record")


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
        """Init

        Args:
            config: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.config = config
        self._initialized = False
        self._model_modules: List[str] = []

    def register_models(
        self,
        *modules: Annotated[
            str, Doc("Dotted module paths containing Tortoise models.")
        ],
    ) -> None:
        """Register model modules to be discovered on init."""
        self._model_modules.extend(modules)

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

    def _build_tortoise_config(self) -> dict:
        """Build Tortoise Config

        Returns:
            [description]

        Raises:
            [description]
        """
        cfg = self.config
        modules = self._model_modules or ["__main__"]
        credentials: Dict[str, Any] = {
            "pool_size": cfg.pool_size,
            "max_overflow": cfg.max_overflow,
            "pool_recycle": cfg.pool_recycle,
            "echo": cfg.echo,
        }
        if cfg.backend.value == "sqlite":
            credentials["file_path"] = cfg.url.replace("sqlite://", "")
        else:
            credentials["database"] = cfg.url
            credentials["ssl"] = cfg.ssl
            credentials["ssl_ca"] = cfg.ssl_ca
            credentials["ssl_cert"] = cfg.ssl_cert
            credentials["ssl_key"] = cfg.ssl_key

        return {
            "connections": {
                "default": {
                    "engine": f"tortoise.backends.{cfg.backend.value}",
                    "credentials": credentials,
                }
            },
            "apps": {
                "models": {
                    "models": modules,
                    "default_connection": "default",
                }
            },
            "timezone": cfg.timezone,
        }


def setup_record(
    app,
    config: Annotated[DatabaseConfig, Doc("Database configuration.")],
    *,
    model_modules: Annotated[
        Optional[List[str]], Doc("List of dotted model module paths.")
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
