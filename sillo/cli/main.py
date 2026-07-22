#!/usr/bin/env python
"""
sillo CLI - Main entry point for all CLI commands.
"""

import click

from sillo.__main__ import __version__
from sillo.cli.commands import new, ping, run, shell, urls

CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "auto_envvar_prefix": "sillo",
}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__, prog_name="sillo")
def cli():
    """
    sillo CLI - Command line tools for the sillo framework.

    This is the root command group for the sillo CLI application. It serves as
    the main entry point that aggregates all subcommands such as new, run, urls,
    ping, and shell into a unified command-line interface.

    The command group is configured with custom context settings that enable
    short-form help flags (-h) and automatic environment variable prefixing
    using the 'sillo' prefix for all options.

    Returns:
        None. This function acts as a Click group dispatcher and does not
        return a value. Subcommands are invoked through Click's routing.

    Raises:
        click.UsageError: If an unknown subcommand is provided by the user.
        SystemExit: If the --version flag is passed, Click exits after printing.
    """
    pass


# Import and register all CLI commands

# Register commands
cli.add_command(new)
cli.add_command(run)
cli.add_command(urls)
cli.add_command(ping)
cli.add_command(shell)
