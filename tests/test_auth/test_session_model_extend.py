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


class TestMarkActivity:
    async def test_updates_last_activity(self):
        session = await make_session()
        before = session.last_activity
        await session.mark_activity()
        reloaded = await Session.get(id=session.id)
        assert reloaded.last_activity >= before


class TestTerminate:
    async def test_marks_the_session_inactive(self):
        session = await make_session()
        assert session.is_active is True
        await session.terminate()
        reloaded = await Session.get(id=session.id)
        assert reloaded.is_active is False


class TestTerminateAllForUser:
    async def test_deactivates_only_that_users_active_sessions(self):
        mine_a = await make_session(user_id=1, session_key="a")
        mine_b = await make_session(user_id=1, session_key="b")
        already_off = await make_session(user_id=1, session_key="c", is_active=False)
        theirs = await make_session(user_id=2, session_key="d")

        count = await Session.terminate_all_for_user(1)

        assert count == 2  # a and b were active; already_off was not
        for s in (mine_a, mine_b, already_off):
            reloaded = await Session.get(id=s.id)
            assert reloaded.is_active is False
        assert (await Session.get(id=theirs.id)).is_active is True


class TestCleanupExpired:
    async def test_deactivates_only_expired_active_sessions(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        future = datetime.now(timezone.utc) + timedelta(hours=1)

        expired = await make_session(session_key="expired", expires_at=past)
        still_valid = await make_session(session_key="valid", expires_at=future)
        already_inactive = await make_session(
            session_key="inactive", expires_at=past, is_active=False
        )

        count = await Session.cleanup_expired()

        assert count == 1  # only the active-and-expired one
        assert (await Session.get(id=expired.id)).is_active is False
        assert (await Session.get(id=still_valid.id)).is_active is True
        assert (await Session.get(id=already_inactive.id)).is_active is False
