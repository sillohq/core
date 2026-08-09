from pathlib import Path

import pytest

from sillo import SilloApp
from sillo.templating import TemplateConfig, TemplateEngine, render
from sillo.templating.middleware import TemplateContextMiddleware
from sillo.testclient import TestClient


@pytest.fixture
def template_engine():
    config = TemplateConfig(
        template_dir=Path("tests/templates"),
        custom_filters={"currency": lambda value, symbol="$": f"{symbol}{value:,.2f}"},
    )
    engine = TemplateEngine()
    engine.setup_environment(config)
    return engine


@pytest.fixture
def app():
    app = SilloApp()

    async def user_context(request):
        return {"user": {"name": "Test User"}}

    app.use(
        TemplateContextMiddleware(
            default_context={"app_name": "Test App"}, context_processor=user_context
        )
    )

    @app.get("/")
    async def home(request, response):
        return await render(
            "welcome.html", {"name": "Test User", "message": "Welcome to our test app!"}
        )

    return app


@pytest.mark.asyncio
async def test_template_rendering(template_engine):
    """Test basic template rendering with context"""
    content = await template_engine.render(
        "welcome.html", {"name": "User", "message": "Hello!"}
    )
    assert "Welcome, User!" in content
    assert "Hello!" in content


@pytest.mark.asyncio
async def test_template_inheritance(template_engine):
    """Test template inheritance and block overriding"""
    content = await template_engine.render(
        "welcome.html", {"name": "User", "message": "Test message"}
    )
    assert "<title>Welcome</title>" in content
    assert "<main>" in content
    assert "Test message" in content


@pytest.mark.asyncio
async def test_template_filters(template_engine):
    """Test custom template filters"""
    content = await template_engine.render(
        "product.html",
        {"name": "Test Product", "price": 99.99, "description": "A" * 150},
    )
    assert "€99.99" in content
    assert "A" * 97 + "..." in content


@pytest.mark.asyncio
async def test_template_context_middleware(app):
    """Test template context middleware"""
    async with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Welcome, Test User!" in response.text
        assert "Welcome to our test app!" in response.text
