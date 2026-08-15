"""Regression for ``Session.extend()``.

``expires_at`` is a ``DatetimeField``, and ``extend()`` assigned
``datetime.now(...).timestamp() + seconds`` to it, which is a float. Nothing
called it, in the suite or anywhere else, so the mismatch sat there: the write
went to a datetime column and ``is_expired`` then compared a datetime against
a float.
"""

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo.auth.session_auth.models import Session

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


@pytest.fixture(autouse=True)
async def session_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["sillo.auth.session_auth.models"]},
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


async def make_session(**overrides):
    defaults = dict(
        user_id=1,
        session_key="key-1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    defaults.update(overrides)
    return await Session.create(**defaults)


class TestExtend:
    async def test_stores_a_datetime(self):
        session = await make_session()
        await session.extend(3600)
        assert isinstance(session.expires_at, datetime)

    async def test_the_new_expiry_survives_a_reload(self):
        session = await make_session()
        await session.extend(7200)
        reloaded = await Session.get(id=session.id)
        assert isinstance(reloaded.expires_at, datetime)

    async def test_moves_the_expiry_forward_by_the_requested_amount(self):
        session = await make_session()
        before = datetime.now(timezone.utc)
        await session.extend(3600)
        delta = (await Session.get(id=session.id)).expires_at - before
        # A second of slack for the round trip; the point is that it landed an
        # hour out rather than at an epoch-second interpreted as a date.
        assert timedelta(minutes=59) < delta < timedelta(minutes=61)

    async def test_is_expired_still_works_afterwards(self):
        session = await make_session()
        await session.extend(3600)
        # This raised TypeError comparing a datetime to a float.
        assert (await Session.get(id=session.id)).is_expired is False

    async def test_an_extended_session_that_has_passed_reads_as_expired(self):
        session = await make_session()
        await session.extend(-3600)
        assert (await Session.get(id=session.id)).is_expired is True
