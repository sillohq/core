"""Coverage for sillo.auth.apikey.models: key generation/verification helpers,
the ApiKey model's expiry/mark_used/revoke, and ApiKeyManager's create/verify/
get_for_user/revoke_all_for_user, none of which had any prior test coverage.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo.auth.apikey.models import (
    ApiKey,
    ApiKeyManager,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


@pytest.fixture(autouse=True)
async def apikey_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["sillo.auth.apikey.models"]},
    )
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


def _future():
    return datetime.now(timezone.utc) + timedelta(hours=1)


def _past():
    return datetime.now(timezone.utc) - timedelta(hours=1)


def test_generate_api_key_shape():
    full_key, raw, key_hash = generate_api_key(prefix="acme")
    assert full_key == f"acme_{raw}"
    assert hash_api_key(full_key) == key_hash


def test_verify_api_key_true_and_false():
    full_key, _, key_hash = generate_api_key()
    assert verify_api_key(full_key, key_hash) is True
    assert verify_api_key("wrong-key", key_hash) is False


async def test_apikey_is_expired_property():
    no_expiry = await ApiKey.create(name="n", key_hash="h1", user_id=1)
    assert no_expiry.is_expired is False

    expired = await ApiKey.create(
        name="n", key_hash="h2", user_id=1, expires_at=_past()
    )
    assert expired.is_expired is True

    not_expired = await ApiKey.create(
        name="n", key_hash="h3", user_id=1, expires_at=_future()
    )
    assert not_expired.is_expired is False


async def test_apikey_mark_used_sets_timestamp():
    key = await ApiKey.create(name="n", key_hash="h4", user_id=1)
    assert key.last_used_at is None

    await key.mark_used()

    refreshed = await ApiKey.get(id=key.id)
    assert refreshed.last_used_at is not None


async def test_apikey_revoke_deactivates():
    key = await ApiKey.create(name="n", key_hash="h5", user_id=1)
    assert key.is_active is True

    await key.revoke()

    refreshed = await ApiKey.get(id=key.id)
    assert refreshed.is_active is False


async def test_manager_create_key_returns_working_full_key():
    manager = ApiKeyManager()
    full_key, apikey = await manager.create_key(user_id=1, name="ci")

    assert apikey.name == "ci"
    assert verify_api_key(full_key, apikey.key_hash) is True


async def test_manager_verify_success_updates_last_used():
    manager = ApiKeyManager()
    full_key, apikey = await manager.create_key(user_id=1, name="ci")

    verified = await manager.verify(full_key)

    assert verified is not None
    assert verified.id == apikey.id
    assert verified.last_used_at is not None


async def test_manager_verify_rejects_unknown_key():
    manager = ApiKeyManager()
    assert await manager.verify("sillo_does-not-exist") is None


async def test_manager_verify_rejects_expired_key():
    manager = ApiKeyManager()
    full_key, apikey = await manager.create_key(
        user_id=1, name="ci", expires_at=_past()
    )
    assert await manager.verify(full_key) is None


async def test_manager_get_for_user_only_returns_active_keys_for_that_user():
    manager = ApiKeyManager()
    await manager.create_key(user_id=1, name="mine")
    await manager.create_key(user_id=2, name="theirs")
    _, revoked = await manager.create_key(user_id=1, name="revoked")
    await revoked.revoke()

    keys = await manager.get_for_user(1)

    assert [k.name for k in keys] == ["mine"]


async def test_manager_revoke_all_for_user():
    manager = ApiKeyManager()
    await manager.create_key(user_id=1, name="a")
    await manager.create_key(user_id=1, name="b")
    await manager.create_key(user_id=2, name="c")

    count = await manager.revoke_all_for_user(1)

    assert count == 2
    remaining_active = await manager.get_for_user(1)
    assert remaining_active == []
    other_user_active = await manager.get_for_user(2)
    assert len(other_user_active) == 1
