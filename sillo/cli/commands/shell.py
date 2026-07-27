#!/usr/bin/env python
"""
sillo CLI - Interactive shell command.
"""

import code
import sys
from typing import Any

import click

try:
    import IPython  # noqa: F401
    from IPython.terminal.embed import InteractiveShellEmbed
except ImportError:
    InteractiveShellEmbed = None  # type: ignore[assignment]

from sillo.cli.utils import (
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
    Start an interactive shell with the sillo app context loaded.

    This provides an interactive environment where you can:
    - Access your app instance as 'app'
    - Test routes and handlers
    - Inspect app state
    - Debug and experiment with your application

    The shell automatically attempts to import and expose useful classes such
    as the test Client, Request, and Response for convenient interactive testing.
    IPython is preferred if available, otherwise falls back to the standard
    Python interactive console.

    Examples:
      sillo shell --app myapp.main:app
      sillo shell --app myapp.main:app --ipython

    Args:
        app_path: The application module path in 'module:app_variable' format,
            specifying where the sillo app instance can be imported from.
        ipython: Whether to force the use of IPython shell. If True and IPython
            is not available, falls back to the regular Python shell with a
            warning message. Defaults to False for auto-detection.

    Returns:
        None. The function starts an interactive shell session that blocks until
        the user exits via 'exit' command or Ctrl+D keystroke.

    Raises:
        SystemExit: If the application instance cannot be loaded from the
            specified app_path, or if an unexpected error occurs during
            shell initialization.
    """
    try:
        # Load app instance
        app = _load_app_from_path(app_path)
        if app is None:
            _echo_error("Could not load the app instance. Please check your app_path.")
            sys.exit(1)

        _echo_info(f"Loaded app: {app}")

        # Prepare the shell environment
        shell_vars = {
            "app": app,
            "silloApp": type(app),
        }

        # Try to import common modules that might be useful
        try:
            from sillo.testclient import TestClient as Client

            shell_vars["Client"] = Client
            _echo_info("Test client available as 'Client'")
        except ImportError:
            pass

        try:
            from sillo.core.http import Request, Response

            shell_vars["Request"] = Request  # ty: ignore[invalid-assignment]
            shell_vars["Response"] = Response  # ty: ignore[invalid-assignment]
            _echo_info("Request/Response classes available")
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
    if InteractiveShellEmbed is None:
        return False

    _echo_info("Starting IPython shell...")
    _echo_info("Available variables: app, Client, Request, Response")
    _echo_info("Type 'exit' or press Ctrl+D to exit")

    banner = """
sillo Interactive Shell
=======================
Available variables:
- app: Your sillo application instance
- Client: Test client for making requests
- Request: Request class
- Response: Response class

Examples:
  # Test a route
  async with Client(app) as client:
      resp = await client.get('/')
      print(resp.status_code)
      
  # Inspect app
  print(app.routes)
"""

    shell = InteractiveShellEmbed(banner1=banner)
    shell(local_ns=shell_vars)
    return True


def _try_start_regular_shell(shell_vars: dict[str, Any]) -> bool:
    """Try to start regular Python shell."""
    try:
        _echo_info("Starting Python shell...")
        _echo_info("Available variables: app, Client, Request, Response")
        _echo_info("Type 'exit()' or press Ctrl+D to exit")

        banner = """
sillo Interactive Shell
=======================
Available variables:
- app: Your sillo application instance
- Client: Test client for making requests
- Request: Request class
- Response: Response class
"""

        console = code.InteractiveConsole(shell_vars)
        console.interact(banner=banner)
        return True

    except Exception:
        return False


if __name__ == "__main__":
    shell()
