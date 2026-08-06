"""sillo.admin.templating — Jinja2 template rendering for admin views."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # The fallbacks below rebind these names to None, which a type checker
    # then carries into every use. It only sees the real imports.
    from jinja2 import Environment, FileSystemLoader

    HAS_JINJA2 = True
else:
    try:
        from jinja2 import Environment, FileSystemLoader

        HAS_JINJA2 = True
    except ImportError:
        HAS_JINJA2 = False
        Environment = None
        FileSystemLoader = None

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = None

if HAS_JINJA2:
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

    Raises:
        ImportError: If jinja2 is not installed.
    """
    if _env is None:
        raise ImportError(
            "Admin templating requires jinja2. "
            "Install with: pip install 'sillo[templating]' or pip install jinja2"
        )
    return _env.get_template(name).render(**ctx)
