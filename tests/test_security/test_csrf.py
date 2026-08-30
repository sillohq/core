"""
End-to-end CSRF middleware tests (no mocks, full network flow)
"""

import warnings

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.security.csrf import CSRFConfig, CSRFMiddleware


def test_protected_request_missing_token(test_client_factory):
    """POST to protected route without CSRF should fail."""
    csrf_config = CSRFConfig(enabled=True, secret_key="secret")
    app = SilloApp()
    app.use(CSRFMiddleware(config=csrf_config))

    @app.post("/protected")
    async def protected(ctx: HttpContext):
        return json({"status": "protected"})

    with test_client_factory(app) as client:
        res = client.post("/protected", data={"field": "x"})
        assert res.status_code == 403
        assert "CSRF" in res.text


def test_protected_request_valid_token(test_client_factory):
    """POST to protected route with valid CSRF token should pass."""
    csrf_config = CSRFConfig(enabled=True, secret_key="secret")
    app = SilloApp()
    app.use(CSRFMiddleware(config=csrf_config))

    @app.get("/csrf-token")
    async def get_token(ctx: HttpContext):
        token = getattr(ctx.state, "csrf_token", None)
        return json({"token": token})

    @app.post("/protected")
    async def protected(ctx: HttpContext):
        return json({"status": "protected"})

    with test_client_factory(app) as client:
        token_resp = client.get("/csrf-token")
        token = token_resp.json()["token"]
        cookie = token_resp.cookies.get("csrftoken")

        headers = {
            "X-CSRFToken": token,
            "content-type": "application/x-www-form-urlencoded",
        }
        cookies = {"csrftoken": cookie}
        res = client.post(
            "/protected", headers=headers, cookies=cookies, data={"_": "ok"}
        )

        assert res.status_code == 200
        assert res.json() == {"status": "protected"}


def test_protected_request_invalid_token(test_client_factory):
    """POST to protected route with wrong CSRF token should fail."""
    csrf_config = CSRFConfig(enabled=True, secret_key="secret")
    app = SilloApp()
    app.use(CSRFMiddleware(config=csrf_config))

    @app.get("/csrf-token")
    async def get_token(ctx: HttpContext):
        token = getattr(ctx.state, "csrf_token", None)
        return json({"token": token})

    @app.post("/protected")
    async def protected(ctx: HttpContext):
        return json({"status": "protected"})

    with test_client_factory(app) as client:
        token_resp = client.get("/csrf-token")
        cookie = token_resp.cookies.get("csrftoken")

        bad_token = "tampered-token"
        headers = {
            "X-CSRFToken": bad_token,
            "content-type": "application/x-www-form-urlencoded",
        }
        cookies = {"csrftoken": cookie}
        res = client.post("/protected", headers=headers, cookies=cookies)

        assert res.status_code == 403
        assert "incorrect" in res.text.lower()


def test_cookie_is_reset_on_response(test_client_factory):
    """Every response should set or refresh CSRF cookie."""
    csrf_config = CSRFConfig(enabled=True, secret_key="secret")
    app = SilloApp()
    app.use(CSRFMiddleware(config=csrf_config))

    @app.get("/csrf-token")
    async def get_token(ctx: HttpContext):
        token = getattr(ctx.state, "csrf_token", None)
        return json({"token": token})

    with test_client_factory(app) as client:
        first = client.get("/csrf-token")
        token_1 = first.cookies["csrftoken"]

        second = client.get("/csrf-token")
        token_2 = second.cookies["csrftoken"]

        assert token_1 != token_2 or token_2 is not None


def test_csrf_custom_configuration(test_client_factory):
    """Test CSRF middleware with custom configuration."""
    csrf_config = CSRFConfig(
        enabled=True,
        secret_key="secret",
        cookie_name="custom_csrf",
        header_name="X-Custom-CSRF",
        cookie_path="/custom",
        cookie_secure=True,
        cookie_httponly=False,
    )
    app = SilloApp()
    app.use(CSRFMiddleware(config=csrf_config))

    @app.get("/csrf-token")
    async def get_token(ctx: HttpContext):
        token = getattr(ctx.state, "csrf_token", None)
        return json({"token": token})

    with test_client_factory(app) as client:
        res = client.get("/csrf-token")
        assert res.status_code == 200
        data = res.json()
        assert "token" in data and data["token"]
        # Check custom cookie name
        assert "custom_csrf" in res.cookies
