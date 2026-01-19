#!/usr/bin/env python
"""
Nexios CLI - Interactive shell command.
"""

import sys
from typing import Any, Optional

import click

from nexios.cli.utils import (
    _echo_error,
    _echo_info,
    _echo_warning,
    _load_app_from_path,
)


@click.command()
@click.option(
    "--app",
    "app_path",
    required=True,
    help="App module path in format 'module:app_variable' (e.g., 'myapp.main:app').",
)
@click.option(
    "--ipython",
    is_flag=True,
    help="Force use of IPython shell (default: auto-detect)",
)
def shell(app_path: str, ipython: bool = False):
    """
    Start an interactive shell with the Nexios app context loaded.

    This provides an interactive environment where you can:
    - Access your app instance as 'app'
    - Test routes and handlers
    - Inspect app configuration
    - Debug and experiment with your application

    Examples:
      nexios shell --app myapp.main:app
      nexios shell --app myapp.main:app --ipython
    """
    try:
        # Load app instance
        app = _load_app_from_path(app_path)
        if app is None:
            _echo_error(
                "Could not load the app instance. Please check your app_path."
            )
            sys.exit(1)

        _echo_info(f"Loaded app: {app}")

        # Prepare the shell environment
        shell_vars = {
            "app": app,
            "NexiosApp": type(app),
            "config": getattr(app, "config", {}),
        }

        # Try to import common modules that might be useful
        try:
            from nexios.testing.client import Client

            shell_vars["Client"] = Client
            _echo_info("Test client available as 'Client'")
        except ImportError:
            pass

        try:
            from nexios.http.request import Request
            from nexios.http.response import Response

            shell_vars["Request"] = Request
            shell_vars["Response"] = Response
            _echo_info("Request/Response classes available")
        except ImportError:
            pass

        try:
            from nexios.config import MakeConfig

            shell_vars["MakeConfig"] = MakeConfig
            _echo_info("MakeConfig available for configuration")
        except ImportError:
            pass

        # Try to start IPython if available or requested
        if ipython:
            if not _try_start_ipython_shell(shell_vars):
                _echo_warning("Falling back to regular Python shell")
                _try_start_regular_shell(shell_vars)
        else:
            if not _try_start_regular_shell(shell_vars):
                _echo_info("IPython not found, trying regular shell")
                _try_start_ipython_shell(shell_vars)

    except Exception as e:
        _echo_error(f"Error starting shell: {e}")
        sys.exit(1)


def _try_start_ipython_shell(shell_vars: dict[str, Any]) -> bool:
    """Try to start IPython shell."""
    try:
        import IPython  # type: ignore # noqa: F401
        from IPython.terminal.embed import InteractiveShellEmbed  # type: ignore

        _echo_info("Starting IPython shell...")
        _echo_info(
            "Available variables: app, config, Client, Request, Response, MakeConfig"
        )
        _echo_info("Type 'exit' or press Ctrl+D to exit")

        banner = """
Nexios Interactive Shell
=======================
Available variables:
- app: Your Nexios application instance
- config: Application configuration
- Client: Test client for making requests
- Request: Request class
- Response: Response class
- MakeConfig: Configuration class

Examples:
  # Test a route
  async with Client(app) as client:
      resp = await client.get('/')
      print(resp.status_code)
      
  # Inspect app
  print(app.routes)
  print(app.config)
"""

        shell = InteractiveShellEmbed(banner1=banner)  # type: ignore
        shell(local_ns=shell_vars)
        return True

    except ImportError:
        return False


def _try_start_regular_shell(shell_vars: dict[str, Any]) -> bool:
    """Try to start regular Python shell."""
    try:
        import code

        _echo_info("Starting Python shell...")
        _echo_info(
            "Available variables: app, config, Client, Request, Response, MakeConfig"
        )
        _echo_info("Type 'exit()' or press Ctrl+D to exit")

        banner = """
Nexios Interactive Shell
=======================
Available variables:
- app: Your Nexios application instance
- config: Application configuration
- Client: Test client for making requests
- Request: Request class
- Response: Response class
- MakeConfig: Configuration class
"""

        console = code.InteractiveConsole(shell_vars)
        console.interact(banner=banner)
        return True

    except Exception:
        return False


if __name__ == "__main__":
    shell()
