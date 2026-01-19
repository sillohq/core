#!/usr/bin/env python
"""
Nexios CLI - Ping route command.
"""

import asyncio
import sys
from typing import Optional

import click

from nexios.cli.utils import (
    _echo_error,
    _echo_info,
    _echo_success,
    _echo_warning,
    _load_app_from_path,
)


try:
    from nexios.testing.client import Client
except ImportError:
    Client = None


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
    Ping a route in the Nexios app to check if it exists (returns status code).

    Examples:
      nexios ping /about --app sandbox:app
    """

    async def _ping():
        try:
            # Load app instance
            app = _load_app_from_path(cli_app_path)
            if app is None:
                _echo_error(f"Could not load app instance.")
                sys.exit(1)
            
            if not Client:
                _echo_error("httpx is not installed. Install with: pip install httpx")
                sys.exit(1)
                return
            
            async with Client(app) as client:
                resp = await client.request(method.upper(), route_path)
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
