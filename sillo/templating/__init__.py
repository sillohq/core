"""
sillo templating system with Jinja2 integration.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, Optional, Union

import jinja2
from jinja2 import Environment, FileSystemLoader, select_autoescape

from sillo.core.http.response import HTMLResponse
from sillo.types import HttpContext

from .middleware import template_context

engine: TemplateEngine | None = None


class TemplateConfig:
    """Template configuration settings."""

    def __init__(
        self,
        template_dir: str | Path = "templates",
        cache_size: int = 100,
        auto_reload: bool = True,
        encoding: str = "utf-8",
        enable_async: bool = True,
        trim_blocks: bool = True,
        lstrip_blocks: bool = True,
        custom_filters: dict[str, Callable[[Any], Any]] = {},
        custom_globals: dict[str, Any] = {},
    ):
        """Init"""
        self.template_dir = template_dir
        self.cache_size = cache_size
        self.auto_reload = auto_reload
        self.encoding = encoding
        self.enable_async = enable_async
        self.trim_blocks = trim_blocks
        self.lstrip_blocks = lstrip_blocks
        self.custom_filters = custom_filters
        self.custom_globals = custom_globals

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_dir": self.template_dir,
            "cache_size": self.cache_size,
            "auto_reload": self.auto_reload,
            "encoding": self.encoding,
            "enable_async": self.enable_async,
            "trim_blocks": self.trim_blocks,
            "lstrip_blocks": self.lstrip_blocks,
            "custom_filters": self.custom_filters,
            "custom_globals": self.custom_globals,
        }


class TemplateEngine:
    """Template engine for rendering Jinja2 templates."""

    def setup_environment(self, config: TemplateConfig = TemplateConfig()):
        """Initialize Jinja2 environment."""
        global engine
        self.config: TemplateConfig = config
        template_dir = Path(self.config.template_dir)
        template_dir.mkdir(parents=True, exist_ok=True)

        self.env = Environment(
            loader=FileSystemLoader(template_dir, encoding=self.config.encoding),
            autoescape=select_autoescape(["html", "xml"]),
            cache_size=self.config.cache_size,
            auto_reload=self.config.auto_reload,
            enable_async=self.config.enable_async,
            trim_blocks=self.config.trim_blocks,
            lstrip_blocks=self.config.lstrip_blocks,
        )

        config_ = self.config.to_dict()
        if config_.get("custom_filters"):
            self.env.filters.update(config_["custom_filters"])
        if config_.get("custom_globals"):
            self.env.globals.update(config_["custom_globals"])
        engine = self

    async def render(
        self, template_name: str, context: dict[str, Any] | None = None, **kwargs
    ) -> str:
        """Render a template with context."""

        context = context or {}
        context.update(kwargs)

        template = self.env.get_template(template_name)
        if self.config.enable_async:
            return await template.render_async(**context)
        return template.render(**context)


async def render(
    template_name: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    request: HttpContext | None = None,
    **kwargs,
) -> HTMLResponse:
    """Render template to response."""
    if not engine:
        raise NotImplementedError("Template Engine Has not been set")

    # Start with provided context
    final_context = context or {}
    final_context.update(kwargs)

    # Provide core request-related utilities if request is available
    if request:
        final_context.setdefault("request", request)
        if hasattr(request, "base_app"):
            final_context.setdefault("url_for", request.base_app.url_for)
        if hasattr(request, "state"):
            final_context.setdefault(
                "csrf_token", getattr(request.state, "csrf_token", None)
            )

            # Merge with existing template context from middleware if available
            middleware_context = getattr(request.state, "template_context", None)
            if middleware_context:
                final_context.update(middleware_context)

    content = await engine.render(template_name, final_context)
    return HTMLResponse(content=content, status_code=status_code, headers=headers)
