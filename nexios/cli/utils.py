#!/usr/bin/env python
"""
Nexios CLI - Shared utilities and helper functions.
"""

import importlib
import importlib.util
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

import click

from nexios.utils.app import get_app_instance

if TYPE_CHECKING:
    from nexios.application import NexiosApp


# Utility functions
def _echo_success(message: str) -> None:
    """Print a success message."""
    click.echo(click.style(f"✓ {message}", fg="green"))


def _echo_error(message: str) -> None:
    """Print an error message."""
    click.echo(click.style(f"✗ {message}", fg="red"), err=True)


def _echo_info(message: str) -> None:
    """Print an info message."""
    click.echo(click.style(f"ℹ {message}", fg="blue"))


def _echo_warning(message: str) -> None:
    """Print a warning message."""
    click.echo(click.style(f"⚠ {message}", fg="yellow"))


def _has_write_permission(path: Path) -> bool:
    """Check if we have write permission for the given path."""
    if path.exists():
        return os.access(path, os.W_OK)
    return os.access(path.parent, os.W_OK)


def _is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def _check_server_installed(server: str) -> bool:
    """Check if the specified server is installed."""
    try:
        subprocess.run([server, "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# Validation functions
def _validate_project_name(ctx, param, value):
    """Validate the project name for directory and Python module naming rules."""
    if not value:
        return value

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", value):
        raise click.BadParameter(
            "Project name must start with a letter and contain only letters, "
            "numbers, and underscores."
        )
    return value


def _validate_project_title(ctx, param, value):
    """Validate that the project title does not contain special characters."""
    if not value:
        return value

    if re.search(r"[^a-zA-Z0-9_\s-]", value):
        raise click.BadParameter(
            "Project title should contain only letters, numbers, spaces, underscores, and hyphens."
        )
    return value


def _validate_host(ctx, param, value):
    """Validate hostname format."""
    if value not in ("localhost", "127.0.0.1") and not re.match(
        r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,61}[a-zA-Z0-9])?$", value
    ):
        raise click.BadParameter(f"Invalid hostname: {value}")
    return value


def _validate_port(ctx, param, value):
    """Validate that the port is within the valid range."""
    if not 1 <= value <= 65535:
        raise click.BadParameter(f"Port must be between 1 and 65535, got {value}.")
    return value


def _validate_app_path(ctx, param, value):
    """Validate module:app format."""
    if value and not re.match(
        r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*:[a-zA-Z0-9_]+$", value
    ):
        raise click.BadParameter(
            f"App path must be in the format 'module:app_variable' or 'module.submodule:app_variable', got {value}."
        )
    return value


def _validate_server(ctx, param, value):
    """Validate server choice."""
    if value and value not in ("uvicorn", "granian"):
        raise click.BadParameter("Server must be either 'uvicorn' or 'granian'")
    return value


def _load_app_from_string(app_path: str) -> "NexiosApp":
    """Load app from module:app format string."""
    if ":" not in app_path:
        raise RuntimeError("App path must be in format 'module:app'")

    # Ensure current directory is in sys.path to allow importing local modules
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    module_name, app_var = app_path.split(":", 1)
    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        raise ImportError(f"Could not import module '{module_name}': {e}") from e

    app = getattr(mod, app_var, None)
    if app is None:
        raise RuntimeError(f"No '{app_var}' found in module '{module_name}'")

    return app


def _load_app_from_path(
    app_path: str
) -> "NexiosApp":
    """
    Load the Nexios app instance from the given app_path (module:app).
    """
    if not app_path:
        raise RuntimeError(
            "App path is required. Please specify it with --app."
        )

    return _load_app_from_string(app_path)


def _parse_cli_args_kwargs(args: Tuple[str, ...]) -> Tuple[list[str], dict[str, Any]]:
    """
    Parse CLI arguments into a list of positional arguments and a dictionary of keyword arguments.
    Example: ('pos1', 'key=value', 'pos2') -> (['pos1', 'pos2'], {'key': 'value'})
    """
    positional = []
    keyword = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            # Try to convert to int, float, or bool if possible
            if value.lower() == "true":
                keyword[key] = True
            elif value.lower() == "false":
                keyword[key] = False
            elif value.isdigit():
                keyword[key] = int(value)
            else:
                try:
                    keyword[key] = float(value)
                except ValueError:
                    keyword[key] = value
        else:
            positional.append(arg)
    return positional, keyword
