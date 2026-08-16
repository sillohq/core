"""What the server prints when it comes up, and when it goes down.

The banner replaces four uvicorn log lines with one block that answers the
questions a developer actually has at that moment: what is running, where do I
open it, is reload on, and how many routes did it find. The last of those is
the one no server prints and everyone wants — a route count that reads zero is
usually the whole explanation for the 404 you are about to investigate.

Written to stderr, alongside the log, so redirecting stdout to capture
application output does not tear the two apart.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from sillo.server import theme


def _route_count(app: Any) -> int | None:
    """Count the routes an application exposes.

    The application handed to the server is rarely the one the user wrote:
    uvicorn wraps it in ``ProxyHeadersMiddleware``, and anything else in the
    chain wraps it again. So this walks down the conventional ``.app`` link
    until it finds something with routes, rather than inspecting only the
    outermost object and reporting nothing.

    Args:
        app: The loaded ASGI application, which may be any callable — the
            server does not require it to be a ``SilloApp``.

    Returns:
        The number of routes, or ``None`` when nothing in the chain presents a
        router this can read. ``None`` is rendered as an omitted line rather
        than a zero, because "I could not tell" and "there are none" mean very
        different things to someone reading a banner.
    """
    seen: set[int] = set()
    current = app

    # Bounded rather than "until None": a middleware that holds a reference to
    # itself would otherwise spin, and no real chain is anywhere near this deep.
    for _ in range(20):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))

        for holder in (getattr(current, "router", None), current):
            routes = getattr(holder, "routes", None)
            if routes is not None:
                try:
                    return len(routes)
                except TypeError:
                    pass

        current = getattr(current, "app", None)

    return None


def describe_target(app: Any) -> str:
    """Render the served application as a short, readable string.

    Args:
        app: Either an import string or an application object.

    Returns:
        The import string as given, or ``module:ClassName`` for an object —
        never a ``<object at 0x…>`` repr, which tells a reader nothing.
    """
    if isinstance(app, str):
        return app
    return f"{type(app).__module__}:{type(app).__name__}"


def _address(host: str, port: int, ssl: bool = False) -> str:
    """Render the URL to open.

    Args:
        host: The bound interface.
        port: The bound port.
        ssl: Whether TLS is configured.

    Returns:
        A URL. ``0.0.0.0`` is shown as ``localhost`` because the literal is not
        something a browser can usefully open, and the point of this line is to
        be clicked.
    """
    scheme = "https" if ssl else "http"
    shown = "localhost" if host in ("0.0.0.0", "::", "") else host
    if ":" in shown and not shown.startswith("["):
        shown = f"[{shown}]"
    return f"{scheme}://{shown}:{port}"


def render(
    *,
    target: str,
    host: str,
    port: int,
    reload: bool = False,
    ssl: bool = False,
    app: Any = None,
    elapsed_ms: float | None = None,
    workers: int = 1,
) -> str:
    """Build the startup banner.

    Args:
        target: The import string being served.
        host: The bound interface.
        port: The bound port.
        reload: Whether the reloader is watching.
        ssl: Whether TLS is configured.
        app: The loaded application, read for a route count.
        elapsed_ms: How long startup took, if it was measured.
        workers: Worker process count.

    Returns:
        The banner, ready to write.
    """
    from sillo import __version__

    mark = theme.paint(theme.GLYPHS["mark"], theme.BRAND)
    name = theme.paint("sillo", theme.VALUE)
    version = theme.paint(__version__, theme.DIM)

    rows: list[tuple[str, str]] = [
        ("app", target),
        ("url", _address(host, port, ssl)),
    ]

    routes = _route_count(app)
    if routes is not None:
        rows.append(("routes", str(routes)))

    mode = "reload" if reload else "serving"
    if workers > 1:
        mode += f" {theme.GLYPHS['dot']} {workers} workers"
    rows.append(("mode", mode))
    rows.append(("pid", str(os.getpid())))

    width = max(len(label) for label, _ in rows)
    lines = [
        "",
        f"  {mark} {name} {version}",
        "",
    ]
    for label, value in rows:
        lines.append(
            f"    {theme.paint(label.ljust(width), theme.LABEL)}   "
            f"{theme.paint(value, theme.VALUE) if label == 'url' else value}"
        )

    footer = "ready" if elapsed_ms is None else f"ready in {elapsed_ms:.0f}ms"
    ready = theme.paint(footer, theme.LEVELS["ready"])
    separator = theme.paint(theme.GLYPHS["dot"], theme.DIM)
    hint = theme.paint("press ctrl-c to stop", theme.DIM)

    lines += ["", f"    {ready}  {separator}  {hint}", ""]
    return "\n".join(lines)


def render_shutdown(
    *, requests: int | None = None, uptime_s: float | None = None
) -> str:
    """Build the line printed once the server has stopped.

    Args:
        requests: Requests served, when the count is known.
        uptime_s: How long the server ran, in seconds.

    Returns:
        A single line, or an empty string when there is nothing worth saying.
    """
    parts: list[str] = []
    if requests is not None:
        parts.append(f"{requests} request{'s' if requests != 1 else ''}")
    if uptime_s is not None:
        parts.append(
            f"{uptime_s:.0f}s uptime"
            if uptime_s < 3600
            else f"{uptime_s / 3600:.1f}h uptime"
        )

    mark = theme.paint(theme.GLYPHS["mark"], theme.DIM)
    summary = f"  {theme.paint(theme.GLYPHS['dot'], theme.DIM)}  ".join(parts)
    tail = f"  {summary}" if summary else ""
    return f"\n  {mark} {theme.paint('stopped', theme.LEVELS['stop'])}{tail}\n"


def write(text: str) -> None:
    """Write banner text to the server's stream.

    Args:
        text: The text to write.
    """
    try:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()
    except (ValueError, OSError):
        pass
