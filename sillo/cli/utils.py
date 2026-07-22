#!/usr/bin/env python
"""
sillo CLI - Shared utilities and helper functions.
"""

import importlib
import importlib.util
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Tuple

import click

if TYPE_CHECKING:
    from sillo.application import silloApp


# Utility functions
def _echo_success(message: str) -> None:
    """
    Print a success message to standard output with green styling.

    Displays a prefixed checkmark symbol followed by the provided message
    text, styled in green using Click's terminal color utilities. This is
    used throughout the CLI to indicate successful operations to the user.

    Args:
        message: The success message string to display to the user. Should
            describe the operation that completed successfully.

    Returns:
        None. The formatted message is printed directly to stdout via
        Click's echo function and does not return any value.

    Raises:
        click.ClickException: If Click's styling or echo functions encounter
            an unrecoverable terminal output error.
    """
    click.echo(click.style(f"✓ {message}", fg="green"))


def _echo_error(message: str) -> None:
    """
    Print an error message to standard error with red styling.

    Displays a prefixed cross symbol followed by the provided message text,
    styled in red using Click's terminal color utilities. The output is
    directed to stderr so that error messages are separated from normal
    program output in shell pipelines and redirections.

    Args:
        message: The error message string to display. Should describe the
            error condition that occurred during CLI operation.

    Returns:
        None. The formatted error message is printed directly to stderr
        via Click's echo function with the err=True flag set.

    Raises:
        click.ClickException: If Click's styling or echo functions encounter
            an unrecoverable terminal output error during writing.
    """
    click.echo(click.style(f"✗ {message}", fg="red"), err=True)


def _echo_info(message: str) -> None:
    """
    Print an informational message to standard output with blue styling.

    Displays a prefixed information symbol followed by the provided message
    text, styled in blue using Click's terminal color utilities. This helper
    is used throughout the CLI to convey informational status updates and
    guidance messages to the user during command execution.

    Args:
        message: The informational message string to display. Typically used
            for status updates, next-step instructions, or progress notes.

    Returns:
        None. The formatted message is printed directly to stdout via
        Click's echo function and does not return any value.

    Raises:
        click.ClickException: If Click's styling or echo functions encounter
            an unrecoverable terminal output error during writing.
    """
    click.echo(click.style(f"ℹ {message}", fg="blue"))


def _echo_warning(message: str) -> None:
    """
    Print a warning message to standard output with yellow styling.

    Displays a prefixed warning symbol followed by the provided message text,
    styled in yellow using Click's terminal color utilities. This helper is
    used throughout the CLI to alert the user about non-fatal issues, degraded
    functionality, or conditions that may require attention but do not prevent
    the command from completing.

    Args:
        message: The warning message string to display. Should describe a
            non-critical issue or condition the user should be aware of.

    Returns:
        None. The formatted warning message is printed directly to stdout
        via Click's echo function and does not return any value.

    Raises:
        click.ClickException: If Click's styling or echo functions encounter
            an unrecoverable terminal output error during writing.
    """
    click.echo(click.style(f"⚠ {message}", fg="yellow"))


def _has_write_permission(path: Path) -> bool:
    """
    Check if the current process has write permission for the given path.

    Examines the filesystem permissions to determine whether the current user
    has write access to the specified path. If the path already exists, it
    checks write access directly on that path. If the path does not exist,
    it checks write access on the parent directory, which determines whether
    new files or directories can be created there.

    Args:
        path: A pathlib.Path object representing the filesystem location to
            check for write permissions. Can be either an existing or
            non-existing path.

    Returns:
        True if the current process has write permission to the path (or its
        parent directory if the path does not exist), False otherwise. The
        return value is a boolean indicating permission availability.

    Raises:
        OSError: If the underlying os.access call encounters a filesystem
            error such as a broken symlink or inaccessible parent directory.
    """
    if path.exists():
        return os.access(path, os.W_OK)
    return os.access(path.parent, os.W_OK)


def _is_port_in_use(host: str, port: int) -> bool:
    """
    Check if a network port is already in use on the specified host.

    Attempts to establish a TCP connection to the given host and port combination.
    If the connection succeeds, it indicates that a process is already listening
    on that port. If the connection fails, the port is available for use. This
    is commonly used before starting a server to avoid port conflicts.

    Args:
        host: The hostname or IP address string to check. Examples include
            '127.0.0.1', 'localhost', or '0.0.0.0'.
        port: The integer port number to check, typically in the range 1-65535.
            Common development ports include 8000, 8080, and 3000.

    Returns:
        True if a TCP connection can be established to the host:port combination,
        indicating the port is currently in use by another process. False if the
        connection attempt fails, indicating the port is available.

    Raises:
        socket.gaierror: If the hostname cannot be resolved to an IP address
            by the system's DNS resolver or hosts file lookup.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def _check_server_installed(server: str) -> bool:
    """
    Check if the specified ASGI server binary is installed and available.

    Runs the server executable with the --version flag to verify that it is
    installed on the system and accessible via the current PATH. This check
    is performed before attempting to start the server to provide early and
    clear feedback to the user about missing dependencies.

    Args:
        server: The name or path of the server executable to check. Expected
            values are 'uvicorn' or 'granian', but any executable name that
            supports the --version flag can be provided.

    Returns:
        True if the server executable is found and runs successfully with the
        --version flag. False if the executable is not found on the PATH or
        if it exits with a non-zero return code.

    Raises:
        OSError: If the subprocess module encounters an unexpected error
            while attempting to spawn the child process for version checking.
    """
    try:
        subprocess.run([server, "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# Validation functions
def _validate_project_name(ctx, param, value):
    """
    Validate the project name for directory and Python module naming rules.

    Ensures that the provided project name conforms to valid Python module
    naming conventions and can safely be used as both a directory name and
    a Python importable module name. The name must start with a letter and
    contain only alphanumeric characters and underscores.

    Args:
        ctx: The Click context object passed automatically by the Click
            framework during command-line argument processing.
        param: The Click parameter object representing the argument being
            validated. Used internally by Click for error reporting.
        value: The raw string value of the project name as provided by the
            user on the command line. May be None if not provided.

    Returns:
        The validated project name string if it passes all naming rules, or
        the original value unchanged if it is empty or None (allowing Click
        to handle the required-field validation separately).

    Raises:
        click.BadParameter: If the project name does not start with a letter
            or contains characters other than letters, numbers, and underscores.
    """
    if not value:
        return value

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", value):
        raise click.BadParameter(
            "Project name must start with a letter and contain only letters, "
            "numbers, and underscores."
        )
    return value


def _validate_project_title(ctx, param, value):
    """
    Validate that the project title does not contain special characters.

    Ensures the project title is safe for display and file content usage by
    restricting it to letters, numbers, spaces, underscores, and hyphens.
    This prevents injection of problematic characters into template files
    and configuration outputs where the title is substituted.

    Args:
        ctx: The Click context object passed automatically by the Click
            framework during command-line argument processing.
        param: The Click parameter object representing the option being
            validated. Used internally by Click for error reporting.
        value: The raw string value of the project title as provided by the
            user on the command line. May be None if not provided.

    Returns:
        The validated project title string if it passes character restrictions,
        or the original value unchanged if it is empty or None.

    Raises:
        click.BadParameter: If the project title contains characters outside
            the allowed set of letters, numbers, spaces, underscores, and
            hyphens.
    """
    if not value:
        return value

    if re.search(r"[^a-zA-Z0-9_\s-]", value):
        raise click.BadParameter(
            "Project title should contain only letters, numbers, spaces, underscores, and hyphens."
        )
    return value


def _validate_host(ctx, param, value):
    """
    Validate hostname format for the server binding address.

    Checks that the provided hostname is either a recognized loopback address
    ('localhost' or '127.0.0.1') or conforms to standard DNS hostname naming
    rules. This prevents invalid or potentially malicious host values from
    being passed to the underlying server process.

    Args:
        ctx: The Click context object passed automatically by the Click
            framework during command-line option processing.
        param: The Click parameter object representing the option being
            validated. Used internally by Click for error reporting.
        value: The raw string value of the hostname as provided by the user
            on the command line.

    Returns:
        The validated hostname string if it passes format checks. The value
        is returned unchanged for further use by the calling command.

    Raises:
        click.BadParameter: If the hostname does not match valid DNS naming
            conventions and is not one of the recognized loopback aliases.
    """
    if value not in ("localhost", "127.0.0.1") and not re.match(
        r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,61}[a-zA-Z0-9])?$", value
    ):
        raise click.BadParameter(f"Invalid hostname: {value}")
    return value


def _validate_port(ctx, param, value):
    """
    Validate that the port is within the valid TCP/UDP port range.

    Ensures the provided port number falls within the standard networking
    port range of 1 to 65535. This prevents invalid port values from being
    passed to the server process, which would cause a runtime failure when
    attempting to bind to the socket.

    Args:
        ctx: The Click context object passed automatically by the Click
            framework during command-line option processing.
        param: The Click parameter object representing the option being
            validated. Used internally by Click for error reporting.
        value: The integer port number as provided by the user on the
            command line.

    Returns:
        The validated port number if it falls within the valid range of
        1 to 65535 inclusive. The value is returned unchanged for further
        use by the calling command.

    Raises:
        click.BadParameter: If the port number is outside the valid range
            of 1 to 65535, with a message indicating the invalid value.
    """
    if not 1 <= value <= 65535:
        raise click.BadParameter(f"Port must be between 1 and 65535, got {value}.")
    return value


def _validate_app_path(ctx, param, value):
    """
    Validate the module:app format string for application loading.

    Ensures the provided app path follows the expected 'module:app_variable'
    format, supporting both simple module references and dotted module paths.
    The format must consist of one or more dot-separated Python identifier
    segments, followed by a colon, followed by a Python identifier for the
    application variable name.

    Args:
        ctx: The Click context object passed automatically by the Click
            framework during command-line option processing.
        param: The Click parameter object representing the option being
            validated. Used internally by Click for error reporting.
        value: The raw string value of the app path as provided by the user.
            Expected format is 'module:app' or 'module.submodule:app'.

    Returns:
        The validated app path string if it matches the expected format.
        Returns unchanged if the value is empty or None, allowing Click's
        required-field validation to handle missing values separately.

    Raises:
        click.BadParameter: If the app path does not match the expected
            'module:app_variable' or 'module.submodule:app_variable' format.
    """
    if value and not re.match(
        r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*:[a-zA-Z0-9_]+$", value
    ):
        raise click.BadParameter(
            f"App path must be in the format 'module:app_variable' or 'module.submodule:app_variable', got {value}."
        )
    return value


def _validate_server(ctx, param, value):
    """
    Validate the ASGI server choice against supported server options.

    Ensures that the selected server is one of the supported ASGI server
    implementations. Currently supported servers are 'uvicorn' for development
    use and 'granian' for production deployments. This validation prevents
    users from specifying unsupported or misspelled server names.

    Args:
        ctx: The Click context object passed automatically by the Click
            framework during command-line option processing.
        param: The Click parameter object representing the option being
            validated. Used internally by Click for error reporting.
        value: The raw string value of the server name as provided by the
            user on the command line.

    Returns:
        The validated server name string if it is one of the supported
        options. Returns unchanged if the value is empty or None, allowing
        Click's default value handling to take effect.

    Raises:
        click.BadParameter: If the server name is not one of the supported
            values ('uvicorn' or 'granian').
    """
    if value and value not in ("uvicorn", "granian"):
        raise click.BadParameter("Server must be either 'uvicorn' or 'granian'")
    return value


def _load_app_from_string(app_path: str) -> "silloApp":
    """
    Load a sillo application instance from a module:app format string.

    Parses the provided app path string into a module name and variable name,
    dynamically imports the specified Python module, and retrieves the
    application object attribute from it. The current working directory is
    added to sys.path if not already present to support importing local
    modules that are not installed as packages.

    Args:
        app_path: A string in the format 'module:app_variable' specifying
            the Python module path and the variable name holding the sillo
            application instance. Supports dotted module paths such as
            'myapp.main:app'.

    Returns:
        The silloApp instance retrieved from the specified module attribute.
        The returned object is the actual application instance that can be
        used for server startup or testing.

    Raises:
        RuntimeError: If the app_path string does not contain a colon
            separator, or if the specified variable name is not found as
            an attribute in the imported module.
        ImportError: If the specified module cannot be imported due to a
            missing module, syntax error, or other import failure.
    """
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


def _load_app_from_path(app_path: str) -> "silloApp":
    """
    Load the sillo app instance from the given app_path (module:app).

    Serves as a high-level wrapper around _load_app_from_string that adds
    input validation before delegating to the lower-level loader. Ensures
    that a non-empty app path is provided before attempting to resolve and
    import the application module.

    Args:
        app_path: A string in the format 'module:app_variable' specifying
            the Python module path and the variable name holding the sillo
            application instance. Must not be empty or None.

    Returns:
        The silloApp instance loaded from the specified module path. This
        is the fully initialized application object ready for server startup
        or test client usage.

    Raises:
        RuntimeError: If the app_path is empty, None, or otherwise falsy,
            indicating that the user did not provide the required --app option.
        ImportError: If the underlying module import fails during loading.
    """
    if not app_path:
        raise RuntimeError("App path is required. Please specify it with --app.")

    return _load_app_from_string(app_path)


def _parse_cli_args_kwargs(args: Tuple[str, ...]) -> Tuple[list[str], dict[str, Any]]:
    """
    Parse CLI arguments into a list of positional arguments and a dictionary of keyword arguments.

    Processes a tuple of raw command-line argument strings, separating them into
    positional arguments (those without an '=' sign) and keyword arguments (those
    containing an '=' sign). Keyword argument values are automatically coerced to
    appropriate Python types including booleans, integers, and floats where possible,
    falling back to string values otherwise.

    Args:
        args: A tuple of raw string arguments from the command line. Each element
            is either a positional value like 'pos1' or a key=value pair like
            'key=value'. The tuple may be empty if no extra arguments are provided.

    Returns:
        A tuple of two elements: a list of positional argument strings in their
        original order, and a dictionary mapping keyword argument names to their
        type-coerced values. Boolean strings 'true'/'false' are case-insensitive.

    Raises:
        ValueError: If a float conversion is attempted but fails during the
            type coercion process for a keyword argument value.
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
