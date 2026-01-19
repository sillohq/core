#!/usr/bin/env python
"""
Nexios CLI - URLs listing command.
"""

import sys
from pathlib import Path

import click

from ..utils import _echo_error, _echo_info, _load_app_from_path


@click.command()
@click.option(
    "--app",
    "app_path",
    required=True,
    help="App module path in format 'module:app_variable'.",
)
def urls(app_path: str):
    """
    List all registered URLs in the Nexios application.
    """
    try:
        # Load app instance
        app = _load_app_from_path(app_path)
        if app is None:
            _echo_error(
                "Could not load the app instance. Please check your app_path."
            )
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
