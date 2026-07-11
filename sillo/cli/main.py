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
    """
    pass


# Import and register all CLI commands

# Register commands
cli.add_command(new)
cli.add_command(run)
cli.add_command(urls)
cli.add_command(ping)
cli.add_command(shell)
