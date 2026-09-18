"""Coverage for ``SessionUserMixin`` -- nothing exercised it directly."""

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo.auth.session_auth.mixins import SessionUserMixin
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


class FakeUser(SessionUserMixin):
    def __init__(self, identity: int):
        self.identity = identity


class TestCreateSession:
    async def test_persists_a_session_scoped_to_the_user(self):
        user = FakeUser(1)
        session = await user.create_session(
            "key-1", ip_address="1.2.3.4", user_agent="pytest", device_name="cli"
        )
        assert session.user_id == 1
        assert session.session_key == "key-1"
        assert session.ip_address == "1.2.3.4"
        assert session.user_agent == "pytest"
        assert session.device_name == "cli"

    async def test_expiry_is_computed_from_duration_seconds(self):
        user = FakeUser(1)
        before = datetime.now(timezone.utc)
        session = await user.create_session("key-1", duration_seconds=60)
        assert timedelta(seconds=59) < session.expires_at - before < timedelta(
            seconds=61
        )


class TestGetActiveSessions:
    async def test_returns_only_this_users_active_unexpired_sessions(self):
        user = FakeUser(1)
        other = FakeUser(2)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        past = datetime.now(timezone.utc) - timedelta(hours=1)

        mine = await Session.create(
            user_id=1, session_key="mine", expires_at=future
        )
        await Session.create(
            user_id=1, session_key="expired", expires_at=past
        )
        await Session.create(
            user_id=1, session_key="inactive", expires_at=future, is_active=False
        )
        await Session.create(
            user_id=2, session_key="theirs", expires_at=future
        )

        sessions = await user.get_active_sessions()

        assert [s.id for s in sessions] == [mine.id]
        assert await other.get_active_sessions()


class TestLogoutEverywhere:
    async def test_terminates_every_session_for_this_user(self):
        user = FakeUser(1)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        a = await Session.create(user_id=1, session_key="a", expires_at=future)
        b = await Session.create(user_id=1, session_key="b", expires_at=future)
        theirs = await Session.create(user_id=2, session_key="c", expires_at=future)

        count = await user.logout_everywhere()

        assert count == 2
        assert (await Session.get(id=a.id)).is_active is False
        assert (await Session.get(id=b.id)).is_active is False
        assert (await Session.get(id=theirs.id)).is_active is True


class TestLogoutSession:
    async def test_terminates_a_matching_session_and_returns_true(self):
        user = FakeUser(1)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        session = await Session.create(
            user_id=1, session_key="mine", expires_at=future
        )

        assert await user.logout_session("mine") is True
        assert (await Session.get(id=session.id)).is_active is False

    async def test_returns_false_when_no_session_matches(self):
        user = FakeUser(1)
        assert await user.logout_session("nope") is False

    async def test_does_not_terminate_another_users_session(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        theirs = await Session.create(
            user_id=2, session_key="theirs", expires_at=future
        )
        user = FakeUser(1)

        assert await user.logout_session("theirs") is False
        assert (await Session.get(id=theirs.id)).is_active is True


class TestActiveSessionCount:
    async def test_counts_only_active_unexpired_sessions_for_this_user(self):
        user = FakeUser(1)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        await Session.create(user_id=1, session_key="a", expires_at=future)
        await Session.create(user_id=1, session_key="b", expires_at=future)
        await Session.create(user_id=1, session_key="c", expires_at=past)
        await Session.create(user_id=2, session_key="d", expires_at=future)

        assert await user.active_session_count() == 2

    async def test_zero_when_no_active_sessions(self):
        user = FakeUser(1)
        assert await user.active_session_count() == 0
