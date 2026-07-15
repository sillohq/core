"""sillo.services.admin.templating — Jinja2 template rendering for admin views."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


def render(name: str, **ctx) -> str:
    """Render template *name* with **ctx as template variables."""
    return _env.get_template(name).render(**ctx)
