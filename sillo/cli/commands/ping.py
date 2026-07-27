#!/usr/bin/env python
"""
sillo CLI - Ping route command.
"""

import asyncio
import sys

import click

from sillo.cli.utils import (
    _echo_error,
    _echo_success,
    _echo_warning,
    _load_app_from_path,
)


def _resolve_client():
    """Import the test client, returning ``None`` when it is unavailable.

    This is deliberately deferred to call time. ``sillo/__main__.py`` imports
    the CLI, so a module-level import here runs while ``sillo`` itself is still
    initialising — and the test client imports ``sillo`` right back, so the
    import would fail on a partially initialised package and silently disable
    this command on every machine, installed httpx or not.

    Returns:
        The ``TestClient`` class, or ``None`` if the optional test-client
        dependencies are not installed.
    """
    try:
        from sillo.testclient import TestClient

        return TestClient
    except ImportError:
        return None


@click.command()
@click.argument("route_path")
@click.option(
    "--app",
    "cli_app_path",
    required=True,
    help="App module path in format 'module:app_variable' (e.g., 'myapp.main:app').",
)
@click.option("--method", default="GET", help="HTTP method to use (default: GET)")
def ping(
    route_path: str,
    cli_app_path: str,
    method: str = "GET",
):
    """
    Ping a route in the sillo app to check if it exists (returns status code).

    Loads the sillo application instance from the specified module path and uses
    an asynchronous test client to send an HTTP request to the given route. The
    response status code is displayed along with a human-readable indication of
    whether the route is reachable, not found, or returning an unexpected status.

    Examples:
      sillo ping /about --app sandbox:app
      sillo ping /api/users --app myapp.main:app --method POST

    Args:
        route_path: The URL path of the route to ping within the application.
            Should begin with a forward slash, e.g., '/about' or '/api/users'.
        cli_app_path: The application module path in 'module:app_variable' format,
            specifying where the sillo app instance can be imported from.
        method: The HTTP method to use for the request. Defaults to 'GET'. Other
            common values include 'POST', 'PUT', 'DELETE', and 'PATCH'.

    Returns:
        None. The function prints the HTTP status code and a success, error, or
        warning message to the console via Click echo utilities.

    Raises:
        SystemExit: If the application cannot be loaded, if httpx is not installed,
            or if an error occurs during the route ping operation.
    """

    async def _ping():
        """
        Asynchronously ping the specified route using the test client.

        This inner async function handles the actual route testing logic. It loads
        the application instance, creates a test client session, sends the HTTP
        request to the target route, and reports the response status code with
        appropriate success, error, or warning messages to the console.

        Returns:
            None. Results are printed to the console via Click echo utilities.

        Raises:
            SystemExit: If the app instance cannot be loaded or if the httpx
                library is not installed for test client functionality.
            Exception: Any exception raised during the HTTP request is caught,
                reported via error message, and causes a system exit with code 1.
        """
        try:
            # Load app instance
            app = _load_app_from_path(cli_app_path)
            if app is None:
                _echo_error("Could not load app instance.")
                sys.exit(1)

            Client = _resolve_client()
            if Client is None:
                _echo_error("httpx is not installed. Install with: pip install httpx")
                sys.exit(1)
                return

            async with Client(app) as client:
                resp = client.request(method.upper(), route_path)
                click.echo(f"{route_path} [{method.upper()}] -> {resp.status_code}")

                if resp.status_code == 200:
                    _echo_success("Route exists and is reachable")
                elif resp.status_code == 404:
                    _echo_error("Route not found (404)")
                else:
                    _echo_warning(f"Unexpected status: {resp.status_code}")

        except Exception as e:
            _echo_error(f"Error pinging route: {str(e)}")
            sys.exit(1)

    asyncio.run(_ping())
