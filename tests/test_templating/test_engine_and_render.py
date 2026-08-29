"""Coverage for sillo.templating.__init__ paths the integration test in
test_templates.py doesn't reach: custom_globals, the sync (non-async)
render path, render()'s NotImplementedError when no engine has been set up,
and render()'s context branches (url_for, csrf_token, and merging
middleware-supplied template_context) — none of which are exercised there
since its route never passes ``ctx=`` to ``render()``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import sillo.templating as templating_module
from sillo.templating import TemplateConfig, TemplateEngine, render
from sillo import json


@pytest.fixture(autouse=True)
def _reset_global_engine():
    original = templating_module.engine
    yield
    templating_module.engine = original


async def test_custom_globals_are_available_in_templates():
    config = TemplateConfig(
        template_dir=Path("tests/templates"),
        custom_globals={"site_name": "MySite"},
    )
    engine = TemplateEngine()
    engine.setup_environment(config)
    # base.html doesn't reference site_name, but the global must be usable
    # from any template without being passed explicitly.
    assert engine.env.globals["site_name"] == "MySite"


async def test_sync_render_path_when_async_is_disabled():
    config = TemplateConfig(template_dir=Path("tests/templates"), enable_async=False)
    engine = TemplateEngine()
    engine.setup_environment(config)
    content = await engine.render("welcome.html", {"name": "User", "message": "hi"})
    assert "Welcome, User!" in content


async def test_render_without_an_engine_raises():
    templating_module.engine = None
    with pytest.raises(NotImplementedError, match="Template Engine"):
        await render("welcome.html", {"name": "x", "message": "y"})


async def test_render_injects_the_context_and_url_for(monkeypatch):
    config = TemplateConfig(template_dir=Path("tests/templates"))
    engine = TemplateEngine()
    engine.setup_environment(config)

    def fake_url_for(*args, **kwargs):
        return "/fake-url"

    class FakeBaseApp:
        url_for = staticmethod(fake_url_for)

    class FakeState:
        csrf_token = "tok-123"
        template_context = {"extra": "value"}

    class FakeContext:
        base_app = FakeBaseApp()
        state = FakeState()

    monkeypatch.setattr(templating_module, "engine", engine)

    captured = {}
    original_render = engine.render

    async def spy_render(template_name, context=None, **kwargs):
        captured.update(context or {})
        return await original_render(template_name, context, **kwargs)

    monkeypatch.setattr(engine, "render", spy_render)

    await render(
        "welcome.html",
        {"name": "User", "message": "hi"},
        ctx=FakeContext(),
    )

    assert captured["ctx"].__class__.__name__ == "FakeContext"
    assert captured["url_for"] is fake_url_for
    assert captured["csrf_token"] == "tok-123"
    assert captured["extra"] == "value"


async def test_template_context_middleware_accepts_a_sync_processor():
    from sillo import SilloApp
    from sillo.templating.middleware import TemplateContextMiddleware
    from sillo.testclient import TestClient

    def sync_processor(ctx):
        return {"greeting": "hi"}

    app = SilloApp()
    app.use(TemplateContextMiddleware(context_processor=sync_processor))

    captured = {}

    @app.get("/")
    async def home(ctx):
        captured["context"] = ctx.state.template_context
        return json({"ok": True})

    with TestClient(app) as client:
        client.get("/")

    assert captured["context"]["greeting"] == "hi"


def test_template_context_factory_returns_a_configured_middleware():
    from sillo.templating import template_context
    from sillo.templating.middleware import TemplateContextMiddleware

    middleware = template_context(default_context={"a": 1})
    assert isinstance(middleware, TemplateContextMiddleware)
    assert middleware.default_context == {"a": 1}


async def test_render_tolerates_a_context_without_state_or_base_app():
    config = TemplateConfig(template_dir=Path("tests/templates"))
    engine = TemplateEngine()
    engine.setup_environment(config)
    templating_module.engine = engine

    class BareContext:
        pass

    response = await render(
        "welcome.html", {"name": "User", "message": "hi"}, ctx=BareContext()
    )
    assert response.status_code == 200
