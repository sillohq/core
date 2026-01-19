#!/usr/bin/env python
"""
Nexios CLI - New project command.
"""

import sys
from pathlib import Path
from typing import Optional

import click

from nexios.__main__ import __version__

from ..utils import (
    _echo_error,
    _echo_info,
    _echo_success,
    _echo_warning,
    _has_write_permission,
    _validate_project_name,
    _validate_project_title,
)


@click.command()
@click.argument("project_name", callback=_validate_project_name, required=True)
@click.option(
    "--output-dir",
    "-o",
    default=".",
    help="Directory where the project should be created.",
    type=click.Path(file_okay=False),
)
@click.option(
    "--title",
    help="Display title for the project (defaults to project name if not provided).",
    callback=_validate_project_title,
)
@click.option(
    "--template",
    "-t",
    type=click.Choice(["basic", "standard", "beta"], case_sensitive=False),
    default="basic",
    help="Template type to use for the project.",
    show_default=True,
)
def new(
    project_name: str,
    output_dir: str,
    title: Optional[str] = None,
    template: str = "basic",
):
    """
    Create a new Nexios project.

    Creates a new Nexios project with the given name in the specified directory.
    The project will be initialized with the selected template structure including
    configuration files and a main application file.

    Available template types:
    - basic: Minimal starter template with essential structure
    - standard: A complete template with commonly used features
    - beta: An advanced template with experimental features
    """
    try:
        output_path = Path(output_dir).resolve()
        project_path = output_path / project_name

        if not project_name.strip():
            _echo_error("Project name cannot be empty.")
            return

        if project_path.exists():
            _echo_error(
                f"Directory {project_path} already exists. Choose a different name or location."
            )
            return

        if not _has_write_permission(output_path):
            _echo_error(
                f"No write permission for directory {output_path}. Choose a different location or run with appropriate permissions."
            )
            return

        project_path.mkdir(parents=True, exist_ok=True)
        _echo_info(
            f"Creating new Nexios project: {project_name} using {template} template"
        )

        template_dir = (
            Path(__file__).parent.parent.parent / "templates" / template.lower()
        )

        if not template_dir.exists():
            _echo_error(
                f"Template directory for '{template}' not found: {template_dir}"
            )
            _echo_error(
                "Please ensure you have the latest version of Nexios installed."
            )
            available_templates = [
                p.name
                for p in (Path(__file__).parent.parent.parent / "templates").glob("*")
                if p.is_dir()
            ]
            if available_templates:
                _echo_info(f"Available templates: {', '.join(available_templates)}")
            return

        for src_path in template_dir.glob("**/*"):
            if src_path.is_dir():
                continue

            rel_path = src_path.relative_to(template_dir)
            dest_path = project_path / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                content = src_path.read_text(encoding="utf-8")
                project_title = title or project_name.replace("_", " ").title()
                content = content.replace("{{project_name}}", project_name)
                content = content.replace("{{project_name_title}}", project_title)
                content = content.replace("{{version}}", __version__)
                dest_path.write_text(content, encoding="utf-8")

            except PermissionError:
                _echo_error(
                    f"Permission denied when writing to {dest_path}. Please check your file permissions."
                )
                return
            except Exception as e:
                _echo_warning(f"Error processing template file {src_path}: {str(e)}")

        env_path = project_path / ".env"
        env_content = [
            "# Environment variables for the Nexios application",
            "DEBUG=True",
            "HOST=127.0.0.1",
            "PORT=4000",
        ]
        env_path.write_text("\n".join(env_content) + "\n", encoding="utf-8")

        _echo_success(f"Project {project_name} created successfully at {project_path}")
        _echo_info("Next steps:")
        _echo_info(f"  1. cd {project_name}")
        _echo_info("  2. pip install -r requirements.txt")
        _echo_info("  3. nexios run")

    except Exception as e:
        _echo_error(f"Error creating project: {str(e)}")
        sys.exit(1)
