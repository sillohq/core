"""sillo.admin.templating — Jinja2 template rendering for admin views."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


def render(name: str, **ctx) -> str:
    """Render a Jinja2 template by name with the given context variables.

    Loads the template from the filesystem loader (pointed at the
    ``templates/`` directory co-located with this module) and renders
    it with the supplied keyword arguments as the template context.

    Args:
        name: Template filename relative to the templates directory,
            e.g. ``"index.html"`` or ``"admin/dashboard.html"``.
        **ctx: Keyword arguments passed as template variables.

    Returns:
        The rendered template string.
    """
    return _env.get_template(name).render(**ctx)
