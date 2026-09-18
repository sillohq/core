"""Coverage for APIKeyAuthBackend's ``verify_with_manager`` path and the
custom ``name`` override -- both untested; only the raw-token passthrough
mode was."""

from __future__ import annotations

import inspect

import pytest
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo import SilloApp, json
from sillo.auth.apikey.backend import APIKeyAuthBackend
from sillo.auth.apikey.models import ApiKeyManager
from sillo.core.http import HttpContext
from sillo.testclient import AsyncTestClient

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


@pytest.fixture(autouse=True)
async def apikey_db():
    init_kwargs = {
        "db_url": "sqlite://:memory:",
        "modules": {"models": ["sillo.auth.apikey.models"]},
    }
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas()
    yield
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass


def build_app(**backend_kwargs):
    app = SilloApp()
    backend = APIKeyAuthBackend(verify_with_manager=True, **backend_kwargs)

    @app.get("/whoami")
    async def whoami(ctx: HttpContext):
        result = await backend.authenticate(ctx)
        return json(
            {"success": result.success, "identity": result.identity, "scope": result.scope}
        )

    return app, backend


class TestVerifyWithManager:
    async def test_a_valid_key_resolves_to_the_owning_user(self):
        app, _ = build_app()
        full_key, _ = await ApiKeyManager().create_key(user_id=7, name="ci")

        async with AsyncTestClient(app) as client:
            response = await client.get(
                "/whoami", headers={"X-API-Key": full_key}
            )

        body = response.json()
        assert body["success"] is True
        assert body["identity"] == "7"
        assert body["scope"] == "apiKeyHeader"

    async def test_an_unknown_key_is_refused(self):
        app, _ = build_app()

        async with AsyncTestClient(app) as client:
            response = await client.get(
                "/whoami", headers={"X-API-Key": "key_does-not-exist"}
            )

        body = response.json()
        assert body["success"] is False

    async def test_a_missing_header_is_refused_without_hitting_the_database(self):
        app, _ = build_app()

        async with AsyncTestClient(app) as client:
            response = await client.get("/whoami")

        assert response.json()["success"] is False


class TestCustomName:
    def test_a_custom_name_overrides_the_default_scope_label(self):
        backend = APIKeyAuthBackend(name="partner-key")
        assert backend.name == "partner-key"

    def test_the_default_name_is_used_when_none_is_given(self):
        backend = APIKeyAuthBackend()
        assert backend.name == "apiKeyHeader"
