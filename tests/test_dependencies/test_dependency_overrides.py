"""
Tests for ``app.dependency_overrides`` and ``app.override()`` — swapping a
``Depend(...)`` callable for a test double, FastAPI-style.
"""

from typing import Callable

import pytest

from sillo import SilloApp, json
from sillo.core.dependencies import Depend
from sillo.core.http import HttpContext
from sillo.testclient import TestClient


def get_db(_):
    return "real_db"


def get_user_id(_):
    return "user_123"


def get_user_context(_, user_id: str = Depend(get_user_id, get_context=True)):
    return {"user_id": user_id}


async def async_get_db(_):
    return "real_async_db"


def gen_get_db(_):
    yield "gen_real_db"


async def agen_get_db(_):
    yield "agen_real_db"


def test_override_context_manager_swaps_value(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Inside the ``with`` block, requests see the replacement."""
    app = SilloApp()

    @app.get("/db")
    async def read_db(ctx: HttpContext, db: str = Depend(get_db, get_context=True)):
        return json({"db": db})

    def fake_db(_):
        return "fake_db"

    with test_client_factory(app) as client:
        resp = client.get("/db")
        assert resp.json()["db"] == "real_db"

        with app.override(get_db, fake_db):
            resp = client.get("/db")
            assert resp.json()["db"] == "fake_db"

        resp = client.get("/db")
        assert resp.json()["db"] == "real_db"


def test_override_restores_on_exception(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """The previous mapping comes back even if the block raises."""
    app = SilloApp()

    def fake_db(_):
        return "fake_db"

    assert get_db not in app.dependency_overrides
    with pytest.raises(ValueError), app.override(get_db, fake_db):
        assert app.dependency_overrides[get_db] is fake_db
        raise ValueError("boom")

    assert get_db not in app.dependency_overrides


def test_override_restores_previous_mapping(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """A nested override restores the outer one, not a bare pop."""
    app = SilloApp()

    def fake_db_a(_):
        return "fake_a"

    def fake_db_b(_):
        return "fake_b"

    with app.override(get_db, fake_db_a):
        assert app.dependency_overrides[get_db] is fake_db_a
        with app.override(get_db, fake_db_b):
            assert app.dependency_overrides[get_db] is fake_db_b
        assert app.dependency_overrides[get_db] is fake_db_a

    assert get_db not in app.dependency_overrides


def test_dependency_overrides_dict_direct_assignment(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """The suite-wide pattern — assign and clear directly — also works."""
    app = SilloApp()

    @app.get("/db")
    async def read_db(ctx: HttpContext, db: str = Depend(get_db, get_context=True)):
        return json({"db": db})

    def fake_db(_):
        return "fake_db"

    app.dependency_overrides[get_db] = fake_db
    try:
        with test_client_factory(app) as client:
            resp = client.get("/db")
            assert resp.json()["db"] == "fake_db"
    finally:
        app.dependency_overrides.clear()


def _get_db_lookalike(_):  # same name-free shape as get_db, different identity
    return "shadow_db"


def test_override_matches_by_identity_not_name(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Registering a different-but-similar callable does not affect the real one."""
    app = SilloApp()

    @app.get("/db")
    async def read_db(ctx: HttpContext, db: str = Depend(get_db, get_context=True)):
        return json({"db": db})

    with (
        app.override(_get_db_lookalike, lambda _: "not_used"),
        test_client_factory(app) as client,
    ):
        resp = client.get("/db")
        assert resp.json()["db"] == "real_db"


def test_override_propagates_to_nested_dependency(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Overriding a shared dependency reaches every nested user of it."""
    app = SilloApp()

    @app.get("/context")
    async def read_context(
        ctx: HttpContext, user_context: dict = Depend(get_user_context, get_context=True)
    ):
        return json(user_context)

    def fake_user_id(_):
        return "fake_user"

    with test_client_factory(app) as client:
        resp = client.get("/context")
        assert resp.json()["user_id"] == "user_123"

        with app.override(get_user_id, fake_user_id):
            resp = client.get("/context")
            assert resp.json()["user_id"] == "fake_user"


def test_override_with_no_registered_override_passes_through(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """No entry on ``dependency_overrides`` — the original runs as written."""
    app = SilloApp()

    @app.get("/db")
    async def read_db(ctx: HttpContext, db: str = Depend(get_db, get_context=True)):
        return json({"db": db})

    assert app.dependency_overrides == {}
    with test_client_factory(app) as client:
        resp = client.get("/db")
        assert resp.json()["db"] == "real_db"


def test_override_async_dependency(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """The replacement can be an async function matching the original's shape."""
    app = SilloApp()

    @app.get("/db")
    async def read_db(ctx: HttpContext, db: str = Depend(async_get_db, get_context=True)):
        return json({"db": db})

    async def fake_async_db(_):
        return "fake_async_db"

    with test_client_factory(app) as client, app.override(async_get_db, fake_async_db):
        resp = client.get("/db")
        assert resp.json()["db"] == "fake_async_db"


def test_override_generator_dependency(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """The replacement can be a sync generator matching the original's shape."""
    app = SilloApp()

    @app.get("/db")
    async def read_db(ctx: HttpContext, db: str = Depend(gen_get_db, get_context=True)):
        return json({"db": db})

    def fake_gen_db(_):
        yield "fake_gen_db"

    with test_client_factory(app) as client, app.override(gen_get_db, fake_gen_db):
        resp = client.get("/db")
        assert resp.json()["db"] == "fake_gen_db"


def test_override_async_generator_dependency(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """The replacement can be an async generator matching the original's shape."""
    app = SilloApp()

    @app.get("/db")
    async def read_db(ctx: HttpContext, db: str = Depend(agen_get_db, get_context=True)):
        return json({"db": db})

    async def fake_agen_db(_):
        yield "fake_agen_db"

    with test_client_factory(app) as client, app.override(agen_get_db, fake_agen_db):
        resp = client.get("/db")
        assert resp.json()["db"] == "fake_agen_db"
