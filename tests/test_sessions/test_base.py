"""
Tests for base session interface functionality
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from nexios.config import MakeConfig, set_config
from nexios.session import SessionConfig
from nexios.session.base import BaseSessionInterface


class MockSessionManager(BaseSessionInterface):
    """Mock session manager for testing base functionality"""

    def __init__(self, session_key: str = None):
        super().__init__(session_key)
        self._data = {}

    async def save(self):
        """Mock save method"""
        pass

    async def load(self):
        """Mock load method"""
        pass


class TestBaseSessionInterface:
    """Test base session interface functionality"""

    def setup_method(self):
        """Set up test configuration"""
        config = MakeConfig(
            secret_key="test-secret-key",
            session=SessionConfig(
                session_cookie_name="test_session",
                session_expiration_time=3600,
                session_permanent=False,
                session_refresh_each_request=False,
            ),
        )
        set_config(config)

    def test_session_initialization(self):
        """Test session initialization"""
        session = MockSessionManager("test-key")

        assert session.session_key == "test-key"
        assert session._session_cache == {}
        assert not session.modified
        assert not session.accessed
        assert not session.deleted

    def test_session_getitem_setitem(self):
        """Test getting and setting session items"""
        session = MockSessionManager()

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
        session = MockSessionManager()

        session["key1"] = "value1"
        session["key2"] = "value2"

        del session["key1"]
        assert session.modified is True
        assert session.deleted is True
        assert "key1" not in session._session_cache
        assert session._session_cache["key2"] == "value2"

    def test_session_contains(self):
        """Test 'in' operator for session"""
        session = MockSessionManager()

        session["key1"] = "value1"
        assert "key1" in session
        assert "key2" not in session
        assert session.accessed is True

    def test_session_len(self):
        """Test length of session"""
        session = MockSessionManager()

        assert len(session) == 0
        session["key1"] = "value1"
        session["key2"] = "value2"
        assert len(session) == 2
        assert session.accessed is True

    def test_session_iter(self):
        """Test iterating over session"""
        session = MockSessionManager()

        session["key1"] = "value1"
        session["key2"] = "value2"

        keys = list(session)
        assert set(keys) == {"key1", "key2"}
        assert session.accessed is True

    def test_session_get_method(self):
        """Test session get method"""
        session = MockSessionManager()

        session["key1"] = "value1"

        assert session.get("key1") == "value1"
        assert session.get("key2") is None
        assert session.get("key2", "default") == "default"

    def test_session_keys_values(self):
        """Test session keys and values methods"""
        session = MockSessionManager()

        session["key1"] = "value1"
        session["key2"] = "value2"

        assert set(session.keys()) == {"key1", "key2"}
        assert set(session.values()) == {"value1", "value2"}

    def test_session_get_all(self):
        """Test session get_all method"""
        session = MockSessionManager()

        session["key1"] = "value1"
        session["key2"] = "value2"

        items = dict(session.get_all())
        assert items == {"key1": "value1", "key2": "value2"}

    def test_session_delete_session(self):
        """Test deleting session key"""
        session = MockSessionManager()

        session["key1"] = "value1"
        session["key2"] = "value2"

        session.delete_session("key1")
        assert session.modified is True
        assert session.deleted is True
        assert "key1" not in session._session_cache

    def test_session_is_empty(self):
        """Test session is_empty method"""
        session = MockSessionManager()

        assert session.is_empty() is True

        session["key1"] = "value1"
        assert session.is_empty() is False

    def test_session_clear(self):
        """Test session clear method"""
        session = MockSessionManager()

        session["key1"] = "value1"
        session["key2"] = "value2"

        session.clear()
        assert session._session_cache == {}

    def test_session_get_session_key(self):
        """Test getting session key"""
        session = MockSessionManager("custom-key")
        assert session.get_session_key() == "custom-key"

        session_no_key = MockSessionManager()
        # Should generate a key (in real implementation, but our mock doesn't)
        # For testing, we'll just check it returns something
        key = session_no_key.get_session_key()
        assert key is not None

    def test_session_expiration_time(self):
        """Test session expiration time"""
        session = MockSessionManager()

        # Test default expiration
        expiration = session.get_expiration_time()
        assert expiration is not None
        assert isinstance(expiration, datetime)

    def test_session_has_expired(self):
        """Test session has_expired method"""
        session = MockSessionManager()

        # Should not be expired initially
        assert session.has_expired() is False

        # Set expiration to past time
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        session.set_expiration_time(past_time)
        assert session.has_expired() is True

    def test_session_should_set_cookie(self):
        """Test should_set_cookie property"""
        session = MockSessionManager()

        # Initially should not set cookie if not modified
        assert session.should_set_cookie is False

        # After modification, should set cookie
        session["key1"] = "value1"
        assert session.should_set_cookie is True

    def test_session_set_session_and_get_session(self):
        """Test set_session and get_session methods"""
        session = MockSessionManager()

        session.set_session("key1", "value1")
        assert session.get_session("key1") == "value1"
        assert session.modified is True
        assert session.accessed is True

    def test_session_str_method(self):
        """Test session string representation"""
        session = MockSessionManager()

        session["key1"] = "value1"
        str_repr = str(session)
        assert "Sesion" in str_repr  # Note: There's a typo in the original code
        assert "key1" in str_repr
