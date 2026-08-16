"""Sillo's ASGI server: uvicorn, wearing Sillo's face.

uvicorn is kept because it is excellent and because replacing a battle-tested
HTTP implementation to change some strings would be indefensible. What is
replaced is everything above the protocol: the logging configuration, the
lifecycle announcements, the access log, and the startup output.

Three seams do it, and all three are deliberate rather than monkey-patched:

- :class:`SilloConfig` overrides ``load()`` to wrap the loaded application in
  the access logger, and ``configure_logging()`` to install Sillo's log
  configuration instead of uvicorn's.
- :class:`SilloServer` overrides ``_log_started_message`` to print the banner
  in place of uvicorn's one-line announcement, and ``shutdown`` to add the
  closing card.
- :mod:`sillo.server.logs` translates whatever uvicorn still says on its own.

Nothing here reaches into uvicorn's protocol implementations or reassigns its
module attributes, so a uvicorn upgrade that changes an internal cannot break
this quietly — at worst a translation stops matching, and the message reappears
in uvicorn's own words rather than vanishing.
"""

from __future__ import annotations

from typing import Any


def _require_uvicorn():
    """Import uvicorn, or explain how to get it.

    Returns:
        The ``uvicorn`` module.

    Raises:
        RuntimeError: If uvicorn is not installed, carrying the install
            command rather than a bare ``ImportError`` from three frames down.
    """
    try:
        import uvicorn
    except ImportError as error:  # pragma: no cover - depends on the install
        raise RuntimeError(
            "The Sillo server needs uvicorn, which is not installed.\n"
            "  uv add uvicorn      (or: pip install uvicorn)"
        ) from error
    return uvicorn


def _classes() -> tuple[type, type]:
    """Import the Config and Server subclasses.

    Imported here rather than at module scope so that ``import sillo.server``
    does not pull in uvicorn. A project serving with something else should not
    be made to install it.

    Returns:
        ``(SilloConfig, SilloServer)``.
    """
    _require_uvicorn()
    from sillo.server._uvicorn import SilloConfig, SilloServer

    return SilloConfig, SilloServer


def run(
    app: Any,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    workers: int = 1,
    log_level: str = "info",
    access_log: bool = True,
    show_banner: bool = True,
    inspect: bool = True,
    **uvicorn_options: Any,
) -> None:
    """Serve an application with the Sillo server.

    The entry point behind ``sillo serve``, and usable directly::

        from sillo.server import run

        run("app.main:app", port=8080, reload=True)

    Args:
        app: An import string, or an application object. Reload and multiple
            workers both need an import string — the process that ends up
            serving is not the one that was configured, so it has to be able to
            import the application rather than inherit it.
        host: Interface to bind.
        port: Port to bind. ``0`` asks the OS for a free one, and the banner
            reports what it chose.
        reload: Restart when source files change.
        workers: Worker processes.
        log_level: Lowest level to log.
        access_log: Write a line per request, with its duration.
        show_banner: Print the startup banner and the shutdown card.
        inspect: Mount the request inspector and make each access line a
            clickable link to it. Only honoured on a loopback address; see
            :mod:`sillo.server.inspector` for why.
        **uvicorn_options: Anything else ``uvicorn.Config`` accepts, forwarded
            untouched.

    Raises:
        RuntimeError: If uvicorn is not installed, or if reload or multiple
            workers were asked for without an import string.
    """
    config_class, server_class = _classes()

    if (reload or workers > 1) and not isinstance(app, str):
        raise RuntimeError(
            "reload and workers need an import string such as 'app.main:app', "
            "because the worker process has to import the application rather "
            "than inherit it. Pass the string, or drop reload/workers."
        )

    # `log_config=None` is what tells SilloConfig.configure_logging to install
    # Sillo's configuration: uvicorn's parameter defaults to its own dict, so
    # None is the only value that unambiguously means "not the caller's". A
    # caller who passed their own in **uvicorn_options keeps it.
    uvicorn_options.setdefault("log_config", None)

    config = config_class(
        app,
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=log_level,
        sillo_access_log=access_log,
        sillo_banner=show_banner,
        sillo_inspect=inspect,
        **uvicorn_options,
    )
    server = server_class(config)

    if config.should_reload:
        from uvicorn.supervisors import ChangeReload

        _supervise(ChangeReload, config, server)
    elif config.workers > 1:
        from uvicorn.supervisors import Multiprocess

        _supervise(Multiprocess, config, server)
    else:
        server.run()


def _supervise(supervisor_class: Any, config: Any, server: Any) -> None:
    """Run the server under one of uvicorn's process supervisors.

    uvicorn has changed this constructor between releases: older versions take
    ``(config, target, sockets)`` and newer ones take ``(config, sockets)`` and
    build the target themselves. Both are called rather than pinning one, so
    the server keeps working across the range of uvicorn a project might have
    installed instead of failing on a signature.

    Args:
        supervisor_class: ``ChangeReload`` or ``Multiprocess``.
        config: The server configuration.
        server: The server whose ``run`` is the supervised target.

    Raises:
        TypeError: If neither calling convention is accepted, which would mean
            uvicorn changed it a third way and this needs updating.
    """
    sock = config.bind_socket()
    try:
        supervisor = supervisor_class(config, target=server.run, sockets=[sock])
    except TypeError:
        supervisor = supervisor_class(config, sockets=[sock])
    supervisor.run()
