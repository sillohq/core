"""The Sillo ASGI server.

uvicorn handles the HTTP; Sillo handles everything you see. The protocol
implementation is left exactly as it is — replacing a battle-tested HTTP stack
to change some strings would be a bad trade — while the logging configuration,
the lifecycle announcements, the access log and the startup output are Sillo's.

Used by ``sillo serve``, and directly::

    from sillo.server import run

    run("app.main:app", port=8080, reload=True)

Importing this package does not import uvicorn. A project that serves with
something else is not made to install it.
"""

from __future__ import annotations

from typing import Any

__all__ = ["AccessLog", "SilloConfig", "SilloServer", "run"]


def run(app: Any, **options: Any) -> None:
    """Serve an application with the Sillo server.

    See :func:`sillo.server.server.run` for the full signature.

    Args:
        app: An import string such as ``"app.main:app"``, or an application
            object.
        **options: Server options.
    """
    from sillo.server.server import run as _run

    _run(app, **options)


def __getattr__(name: str) -> Any:
    """Resolve the uvicorn-dependent names on first use.

    ``SilloConfig`` and ``SilloServer`` are classes built against uvicorn's, so
    they cannot exist until uvicorn is imported. Deferring that to attribute
    access keeps ``import sillo.server`` free of the dependency while still
    letting the names be imported normally.

    Args:
        name: The attribute being looked up.

    Returns:
        The requested object.

    Raises:
        AttributeError: If the name is not part of this package's API.
    """
    if name in ("SilloConfig", "SilloServer"):
        from sillo.server import _uvicorn

        globals()["SilloConfig"] = _uvicorn.SilloConfig
        globals()["SilloServer"] = _uvicorn.SilloServer
        return globals()[name]

    if name == "AccessLog":
        from sillo.server.access import AccessLog

        globals()["AccessLog"] = AccessLog
        return AccessLog

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
