"""The uvicorn subclasses behind the Sillo server.

Kept in a module of its own, importing uvicorn at module scope, for a reason
that is not stylistic: ``--reload`` and ``--workers`` both start the server in
a *spawned* process, and multiprocessing pickles the configuration to get it
there. A class defined inside a function is a local object with no importable
qualified name, so pickling it fails with ``Can't get local object`` the moment
reload is switched on.

Defining them here makes them ``sillo.server._uvicorn.SilloConfig`` and
``sillo.server._uvicorn.SilloServer``, which pickle by name like any other
class. :mod:`sillo.server` still imports this module lazily, so importing
``sillo.server`` does not require uvicorn.
"""

from __future__ import annotations

import logging
import logging.config
import socket
import time
from collections.abc import Sequence
from typing import Any

import uvicorn

from sillo.server import banner
from sillo.server.access import AccessLog
from sillo.server.logs import logging_config

__all__ = ["SilloConfig", "SilloServer"]


class SilloConfig(uvicorn.Config):
    """uvicorn's configuration, with Sillo's logging and access layer.

    Attributes:
        sillo_access_log: Whether to wrap the application in the access
            logger. Separate from uvicorn's ``access_log`` because that
            flag controls a logger this configuration has already silenced.
        sillo_banner: Whether the server prints its banner.
    """

    def __init__(
        self,
        *args: Any,
        sillo_access_log: bool = True,
        sillo_banner: bool = True,
        **kwargs: Any,
    ) -> None:
        """Configure the server.

        Args:
            *args: Forwarded to ``uvicorn.Config``.
            sillo_access_log: Wrap the application in the access logger.
            sillo_banner: Print the startup banner.
            **kwargs: Forwarded to ``uvicorn.Config``.
        """
        self.sillo_access_log = sillo_access_log
        self.sillo_banner = sillo_banner
        # Held so the banner can report a route count, which means holding
        # the application object rather than only the import string.
        self.sillo_app: Any = None
        super().__init__(*args, **kwargs)

    def configure_logging(self) -> None:
        """Install Sillo's logging configuration.

        Replaces uvicorn's entirely rather than layering on top of it.

        A user-supplied ``log_config`` still wins, and detecting that is
        the subtle part: uvicorn's ``log_config`` parameter *defaults to
        its own dictionary*, not to ``None``, so "the caller passed one"
        cannot be read off the attribute. :func:`run` passes ``None``
        explicitly to mean "use Sillo's", which makes a non-``None`` value
        here unambiguously the caller's choice.
        """
        if self.log_config is not None:
            super().configure_logging()
            return

        # uvicorn accepts `log_level` as a name or a numeric level; the
        # logging document is built from a name.
        configured = self.log_level
        name = (
            logging.getLevelName(configured).lower()
            if isinstance(configured, int)
            else (configured or "info")
        )
        logging.config.dictConfig(logging_config(name))

        if configured is not None:
            level = (
                logging.getLevelName(configured.upper())
                if isinstance(configured, str)
                else configured
            )
            logging.getLogger("uvicorn.error").setLevel(level)

    def load(self) -> None:
        """Load the application and wrap it in the access logger.

        The wrapper goes on last, so it is the outermost layer and measures
        what the client waited for rather than what the innermost handler
        took.
        """
        super().load()
        self.sillo_app = self.loaded_app
        if self.sillo_access_log and self.loaded_app is not None:
            self.loaded_app = AccessLog(self.loaded_app)

class SilloServer(uvicorn.Server):
    """uvicorn's server, announcing itself as Sillo.

    Attributes:
        config: The :class:`SilloConfig` in use.
    """

    def __init__(self, config: Any) -> None:
        """Prepare the server.

        Args:
            config: A :class:`SilloConfig`.
        """
        super().__init__(config)
        self._started_at = time.perf_counter()
        self._boot_started = time.perf_counter()

    def _log_started_message(self, listeners: Sequence[socket.SocketType]) -> None:
        """Print the banner instead of uvicorn's one-line announcement.

        Args:
            listeners: The bound sockets. Read for the real port, which
                matters when the configured port was 0 and the OS chose.
        """
        config = self.config
        if not getattr(config, "sillo_banner", True):
            super()._log_started_message(listeners)
            return

        port = config.port
        if port == 0 and listeners:
            port = listeners[0].getsockname()[1]

        self._started_at = time.perf_counter()
        banner.write(
            banner.render(
                target=banner.describe_target(config.app),
                host=config.host or "127.0.0.1",
                port=port,
                reload=bool(config.reload),
                ssl=config.ssl is not None,
                app=getattr(config, "sillo_app", None),
                elapsed_ms=(time.perf_counter() - self._boot_started) * 1000,
                workers=config.workers or 1,
            )
        )

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        """Start serving, announcing it even when the sockets were pre-bound.

        uvicorn only calls ``_log_started_message`` when it bound the socket
        itself. Under ``--reload`` and ``--workers`` the supervisor binds it in
        the parent and hands it down, so that branch never runs and the server
        comes up saying nothing at all. Announcing it here restores the banner
        on exactly the paths that lost it — and on reload, reprinting it each
        restart is the clearest possible signal that the restart happened.

        Args:
            sockets: Sockets bound by a supervisor, or ``None`` when uvicorn
                binds its own.
        """
        # Restarted here rather than left at construction time, because under a
        # supervisor the server is built in the parent and unpickled in the
        # child: a timer started at construction measures how long the
        # developer took to save the file, and reports it as boot time.
        self._boot_started = time.perf_counter()
        await super().startup(sockets)
        if sockets is not None and getattr(self.config, "sillo_banner", True):
            self._log_started_message(sockets)

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        """Stop the server and print the closing card.

        Args:
            sockets: Forwarded to uvicorn.
        """
        await super().shutdown(sockets)
        self._log_stopped_message()

    def _log_stopped_message(self) -> None:
        """Print the closing card.

        Its own method rather than inline in ``shutdown`` so it is reachable
        without driving uvicorn's entire shutdown sequence — which reads
        ``self.servers`` and ``self.lifespan``, both set up by ``startup``.
        Naming it mirrors ``_log_started_message``, which uvicorn already has.
        """
        if getattr(self.config, "sillo_banner", True):
            banner.write(
                banner.render_shutdown(
                    uptime_s=time.perf_counter() - self._started_at
                )
            )
