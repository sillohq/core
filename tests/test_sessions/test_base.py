"""
Tests for base session interface functionality
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from sillo.session.base import BaseSessionInterface
from sillo.session.session_objects import Session


class MockSessionManager(BaseSessionInterface):
    """Mock session manager for testing base functionality"""

    def __init__(self, config=None):
        super().__init__(config)
        self._data = {}

    async def save(self, session):
        """Mock save method"""
        self._data = session._session_cache.copy()

    async def load(self, session):
        """Mock load method"""
        session._session_cache.update(self._data)


class TestBaseSessionInterface:
    """Test base session interface functionality"""

    def test_session_initialization(self):
        """Test session initialization"""
        manager = MockSessionManager()
        session = Session(manager, "test-key")

        assert session.session_key == "test-key"
        assert session._session_cache == {}
        assert not session.modified
        assert not session.accessed
        assert not session.deleted

    def test_session_getitem_setitem(self):
        """Test getting and setting session items"""
        manager = MockSessionManager()
        session = Session(manager)

        # Test setting a value
        session["key1"] = "value1"
        assert session.modified is True
        assert session.accessed is True
        assert session._session_cache["key1"] == "value1"

        # Test getting a value
        assert session["key1"] == "value1"
        assert session.accessed is True

    def test_session_delitem(self):
        """Test deleting session items"""
        manager = MockSessionManager()
        session = Session(manager)

        session["key1"] = "value1"
        session["key2"] = "value2"

        del session["key1"]
        assert session.modified is True
        assert session.accessed is True
        # Not `deleted`: that means "purge this session", and a session with
        # key2 still in it must survive to be written back. Asserting it was
        # True here described a bug — the flag reached no backend, because
        # Session.save() cleared it before handing the session over.
        assert session.deleted is False
        assert "key1" not in session._session_cache
        assert session._session_cache["key2"] == "value2"

    def test_session_contains(self):
        """Test 'in' operator for session"""
        manager = MockSessionManager()
        session = Session(manager)

        session["key1"] = "value1"
        assert "key1" in session
        assert "key2" not in session
        assert session.accessed is True

    def test_session_len(self):
        """Test length of session"""
        manager = MockSessionManager()
        session = Session(manager)

        assert len(session) == 0
        session["key1"] = "value1"
        session["key2"] = "value2"
        assert len(session) == 2
        assert session.accessed is True

    def test_session_iter(self):
        """Test iterating over session"""
        manager = MockSessionManager()
        session = Session(manager)

        session["key1"] = "value1"
        session["key2"] = "value2"
        session["key3"] = "value3"
        keys = list(session)
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys
        assert session.accessed is True

    def test_session_clear(self):
        """Test clearing session"""
        manager = MockSessionManager()
        session = Session(manager)

        session["key1"] = "value1"
        session["key2"] = "value2"
        session.clear()
        assert len(session) == 0
        assert session.modified is True
        assert session.deleted is True

    def test_session_modified_flag(self):
        """Test modified flag behavior"""
        manager = MockSessionManager()
        session = Session(manager)

        assert not session.modified
        session["key"] = "value"
        assert session.modified


    def test_get_expiration_time(self):
        """Test session expiration time calculation"""
        manager = MockSessionManager()
        session = Session(manager)

        now = datetime.now(timezone.utc)
        exp = session.get_expiration_time()

        assert exp > now

        session.interface.permanent = True
        exp2 = session.get_expiration_time()
        assert exp2 > now

    def test_session_should_set_cookie(self):
        """Test should_set_cookie property"""
        manager = MockSessionManager()
        session = Session(manager)

        assert not session.should_set_cookie

        session["key"] = "value"
        assert session.should_set_cookie

        session.clear()
        assert  session.should_set_cookie

    async def test_async_save_and_load(self):
        """Test async save and load operations"""
        manager = MockSessionManager()

        session = Session(manager)
        session["test"] = "value"
        await session.save()

        session2 = Session(manager)
        await session2.load()

    async def test_session_async_operations(self):
        """Test async session operations"""
        manager = MockSessionManager()

        session = Session(manager)
        session["async_key"] = "async_value"
        await session.save()

        new_session = Session(manager, session.session_key)
        await new_session.load()

        assert new_session["async_key"] == "async_value"

    def test_session_with_custom_session_key(self):
        """Test session with custom session key"""
        manager = MockSessionManager()
        session = Session(manager, "custom-key-123")

        assert session.session_key == "custom-key-123"

    def test_session_is_empty(self):
        """Test is_empty method"""
        manager = MockSessionManager()
        session = Session(manager)

        assert session.is_empty()

        session["key"] = "value"
        assert not session.is_empty()

        session.clear()
        assert session.is_empty()

    async def test_session_save_then_modify(self):
        """Test save then modify scenario"""
        manager = MockSessionManager()

        session = Session(manager)
        session["initial"] = "data"
        await session.save()

        session["new"] = "data2"

        new_session = Session(manager, session.session_key)
        await new_session.load()

        assert new_session["initial"] == "data"
        assert "new" not in new_session

    def test_session_nonexistent_key(self):
        """Test accessing nonexistent key"""
        manager = MockSessionManager()
        session = Session(manager)

        assert session.get("nonexistent") is None
        assert session.get("nonexistent", "default") == "default"

    def test_session_set_get_multiple(self):
        """Test setting and getting multiple keys"""
        manager = MockSessionManager()
        session = Session(manager)

        data = {
            "user_id": 123,
            "username": "testuser",
            "preferences": {"theme": "dark"},
        }

        for key, value in data.items():
            session[key] = value

        for key, value in data.items():
            assert session[key] == value

    async def test_session_persistence_across_instances(self):
        """Test session data persistence across instances"""
        manager = MockSessionManager()

        session1 = Session(manager)
        session1["persistent"] = "data"
        await session1.save()

        session2 = Session(manager, session1.session_key)
        await session2.load()

        assert session2["persistent"] == "data"

    def test_session_repr(self):
        """Test session string representation"""
        manager = MockSessionManager()
        session = Session(manager, "test-key")

        repr_str = repr(session)
        assert "test-key" in repr_str

    def test_session_modified_after_load(self):
        """Test that session is not modified after load"""
        manager = MockSessionManager()

        session = Session(manager)
        session["key"] = "value"
        session.modified = False

        session2 = Session(manager, session.session_key)
        assert not session2.modified

    async def test_session_with_complex_data(self):
        """Test session with complex data types"""
        manager = MockSessionManager()

        complex_data = {
            "user": {"id": 1, "name": "Test"},
            "items": [1, 2, 3],
            "nested": {"a": {"b": {"c": "deep"}}},
        }

        session = Session(manager)
        for key, value in complex_data.items():
            session[key] = value

        await session.save()

        new_session = Session(manager, session.session_key)
        await new_session.load()

        for key, value in complex_data.items():
            assert new_session[key] == value

    def test_session_cookie_properties(self):
        """Test session cookie-related properties"""
        manager = MockSessionManager()
        session = Session(manager)

        assert session.interface.get_cookie_name() == "session_id"
        assert session.interface.get_cookie_domain() is None
        assert session.interface.get_cookie_path() == "/"
        assert session.interface.get_cookie_httponly() is True
        assert session.interface.get_cookie_secure() is False
        assert session.interface.get_cookie_samesite() == "lax"

    def test_session_clear_sets_deleted_flag(self):
        """Test that clear() sets the deleted flag"""
        manager = MockSessionManager()
        session = Session(manager)

        session["key"] = "value"
        assert not session.deleted

        session.clear()
        assert session.deleted

    async def test_session_save_clears_flags(self):
        """Test that save() clears modified and deleted flags"""
        manager = MockSessionManager()

        session = Session(manager)
        session["key"] = "value"
        session.deleted = True

        await session.save()

        assert not session.modified
        assert not session.deleted

    def test_session_with_empty_key(self):
        """Test session with empty string key"""
        manager = MockSessionManager()
        session = Session(manager, "")

        assert session.session_key == ""

    def test_session_get_with_default(self):
        """Test session.get() with default value"""
        manager = MockSessionManager()
        session = Session(manager)

        assert session.get("missing") is None
        assert session.get("missing", "default") == "default"

        session["exists"] = "value"
        assert session.get("exists", "default") == "value"

    async def test_concurrent_session_access(self):
        """Test concurrent access to sessions"""
        manager = MockSessionManager()

        session1 = Session(manager, "shared-key")
        session1["shared"] = "data1"
        await session1.save()

        session2 = Session(manager, "shared-key")
        await session2.load()
        session2["shared"] = "data2"
        await session2.save()

        session3 = Session(manager, "shared-key")
        await session3.load()
        assert session3["shared"] == "data2"

    def test_session_keys_values_items(self):
        """Test session.keys(), .values(), .items() methods"""
        manager = MockSessionManager()
        session = Session(manager)

        session["a"] = 1
        session["b"] = 2

        assert set(session.keys()) == {"a", "b"}
        assert set(session.values()) == {1, 2}
        assert set(session.items()) == {("a", 1), ("b", 2)}



    def test_session_update(self):
        """Test session.update() method"""
        manager = MockSessionManager()
        session = Session(manager)

        session.update({"a": 1, "b": 2})
        assert session["a"] == 1
        assert session["b"] == 2

