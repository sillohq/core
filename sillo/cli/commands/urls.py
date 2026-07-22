#!/usr/bin/env python
"""
sillo CLI - URLs listing command.
"""

import sys

import click

from ..utils import _echo_error, _load_app_from_path


@click.command()
@click.option(
    "--app",
    "app_path",
    required=True,
    help="App module path in format 'module:app_variable'.",
)
def urls(app_path: str):
    """List all registered URLs in the sillo application as a formatted table.

    Loads the sillo application instance from the dotted module path supplied
    via the ``--app`` CLI option, retrieves every registered route from the
    application's routing table, and prints a human-readable table to standard
    output. Each row displays the HTTP methods allowed on the route, the raw
    URL path pattern, the endpoint name, and an optional summary description.
    Routes that lack certain attributes (such as ``methods`` or ``summary``)
    are rendered with sensible placeholder values (``"-"`` or empty string).

    Args:
        app_path: A string in the format ``'module:app_variable'`` that
            identifies the sillo application instance to introspect. The module
            is imported dynamically and the named attribute is resolved to
            obtain the application object.

    Returns:
        None. Output is written directly to standard output via
        :func:`click.echo`.

    Raises:
        SystemExit: Exits with code ``1`` if the application instance cannot be
            loaded from the given path, or if any unexpected error occurs
            during route enumeration or output formatting.
    """
    try:
        # Load app instance
        app = _load_app_from_path(app_path)
        if app is None:
            _echo_error("Could not load the app instance. Please check your app_path.")
            sys.exit(1)

        routes = app.get_all_routes()
        click.echo(f"{'METHODS':<15} {'PATH':<40} {'NAME':<20} {'SUMMARY'}")
        click.echo("-" * 90)
        for route in routes:
            methods = (
                ",".join(route.methods) if getattr(route, "methods", None) else "-"
            )
            path = getattr(route, "raw_path", getattr(route, "path", "-")) or "-"
            name = getattr(route, "name", None) or "-"
            summary = getattr(route, "summary", None) or ""
            click.echo(f"{methods:<15} {path:<40} {name:<20} {summary}")
    except Exception as e:
        _echo_error(f"Error listing URLs: {e}")
        sys.exit(1)
