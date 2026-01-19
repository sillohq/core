#!/usr/bin/env python
"""
Nexios CLI - Run server command.
"""

import os
import subprocess
import sys
import traceback
from ..utils import (
    _echo_error,
    _echo_info,
    _parse_cli_args_kwargs,
    _validate_app_path,
    _validate_host,
    _validate_port,
    _validate_server,
)
from typing import Tuple

import click
@click.command(context_settings={"ignore_unknown_options": True})
@click.option(
    "--host",
    "-h",
    default="127.0.0.1",
    callback=_validate_host,
    help="Host to bind the server to.",
    show_default=True,
)
@click.option(
    "--port",
    "-p",
    default=8000,
    type=int,
    callback=_validate_port,
    help="Port to bind the server to.",
    show_default=True,
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development (uvicorn only).",
)
@click.option(
    "--app",
    "-a",
    "app_path",
    required=True,
    callback=_validate_app_path,
    help="App module path in format 'module:app_variable'.",
)
@click.option(
    "--server",
    "-s",
    type=click.Choice(["uvicorn", "granian"], case_sensitive=False),
    default="uvicorn",
    callback=_validate_server,
    help="Server to use for running the application.",
    show_default=True,
)
@click.option(
    "--workers",
    "-w",
    type=int,
    default=1,
    help="Number of worker processes (granian only).",
    show_default=True,
)
@click.argument("cli_options", nargs=-1, type=click.UNPROCESSED)
def run(
    host: str,
    port: int,
    reload: bool,
    app_path: str,
    server: str,
    workers: int,
    cli_options: Tuple[str, ...],
):
    """
    Run the Nexios application using the specified server.

    Supports both Uvicorn (development) and Granian (production) servers.
    You can also pass additional options as key=value arguments.
    """
    try:
        # Parse CLI options (key=value)
        _, extra_options = _parse_cli_args_kwargs(cli_options)

        # Merge defaults with CLI options (CLI args take precedence)
        options = {
            "host": host,
            "port": port,
            "reload": reload,
            "server": server,
            "workers": workers,
            "app_path": app_path,
        }
        
        # Override defaults if explicitly provided via key=value
        options.update(extra_options)

        # Use app_path from options
        app_path = options.get("app_path", app_path)
        if not app_path:
             _echo_error("App path is required. Please specify it with --app option.")
             sys.exit(1)

        # Support custom_command as either a string or a list (array)
        if "custom_command" in options and options["custom_command"]:
            custom_cmd = options["custom_command"]
            if isinstance(custom_cmd, (list, tuple)):
                subprocess.run(custom_cmd, check=True)  # type: ignore
            else:
                # Assume string, run in shell
                os.system(custom_cmd)
            return

        # Extract merged values
        host = options.get("host", host)
        port = options.get("port", port)
        reload = options.get("reload", reload)
        server = options.get("server", server)
        workers = options.get("workers", workers)

        # Use gunicorn if server is gunicorn
        if server == "gunicorn":
            workers = options.get("workers", 4)
            host = options.get("host", "0.0.0.0")
            port = options.get("port", 8000)
            app_path = options.get("app_path", "main:app")
            cmd = f"gunicorn -w {workers} -b {host}:{port} {app_path}"
            os.system(cmd)
            return

        # Prepare the command based on server choice
        if server == "uvicorn":
            cmd = [
                "uvicorn",
                app_path,
                "--host",
                str(host),
                "--port",
                str(port),
            ]
            if reload:
                cmd.append("--reload")
                _echo_info("Auto-reload enabled (development mode)")
        else:  # granian
            cmd = [
                "granian",
                "--host",
                str(host),
                "--port",
                str(port),
                "--workers",
                str(workers),
                app_path,
            ]
            _echo_info(f"Using {workers} worker process(es)")

        _echo_info(f"Starting Nexios server on http://{host}:{port} using {server}")
        _echo_info(f"Using app module: {app_path}")

        # Run the server
        subprocess.run(cmd, check=True)

    except subprocess.CalledProcessError as e:
        _echo_error(f"Server exited with error: {e}")
        sys.exit(1)
    except Exception as e:
        traceback.print_exc()
        _echo_error(f"Error running server: {str(e)}")
        sys.exit(1)
