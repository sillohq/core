"""
Tests for base session interface functionality
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from nexios.config import MakeConfig, set_config
from nexios.session.base import BaseSessionInterface
from nexios.session.session_objects import Session


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

    def setup_method(self):
        """Set up test configuration"""
        config = MakeConfig(secret_key="test-secret-key")
        set_config(config)
        self.manager = MockSessionManager()

    def test_session_initialization(self):
        """Test session initialization"""
        session = Session(self.manager, "test-key")

        assert session.session_key == "test-key"
        assert session._session_cache == {}
        assert not session.modified
        assert not session.accessed
        assert not session.deleted

    def test_session_getitem_setitem(self):
        """Test getting and setting session items"""
        session = Session(self.manager)

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
        session = Session(self.manager)

        session["key1"] = "value1"
        session["key2"] = "value2"

        del session["key1"]
        assert session.modified is True
        assert session.deleted is True
        assert "key1" not in session._session_cache
        assert session._session_cache["key2"] == "value2"

    def test_session_contains(self):
        """Test 'in' operator for session"""
        session = Session(self.manager)

        session["key1"] = "value1"
        assert "key1" in session
        assert "key2" not in session
        assert session.accessed is True

    def test_session_len(self):
        """Test length of session"""
        session = Session(self.manager)

        assert len(session) == 0
        session["key1"] = "value1"
        session["key2"] = "value2"
        assert len(session) == 2
        assert session.accessed is True

    def test_session_iter(self):
        """Test iterating over session"""
        session = Session(self.manager)

        session["key1"] = "value1"
        session["key2"] = "value2"

        keys = list(session)
        assert set(keys) == {"key1", "key2"}
        assert session.accessed is True

    def test_session_get_method(self):
        """Test session get method"""
        session = Session(self.manager)

        session["key1"] = "value1"

        assert session.get("key1") == "value1"
        assert session.get("key2") is None
        assert session.get("key2", "default") == "default"

    def test_session_keys_values(self):
        """Test session keys and values methods"""
        session = Session(self.manager)

        session["key1"] = "value1"
        session["key2"] = "value2"

        assert set(session.keys()) == {"key1", "key2"}
        assert set(session.values()) == {"value1", "value2"}

    def test_session_delete_key(self):
        """Test deleting session key via delete method"""
        session = Session(self.manager)

        session["key1"] = "value1"
        session["key2"] = "value2"

        session.delete("key1")
        assert session.modified is True
        assert session.deleted is True
        assert "key1" not in session._session_cache

    def test_session_is_empty(self):
        """Test session is_empty method"""
        session = Session(self.manager)

        assert session.is_empty() is True

        session["key1"] = "value1"
        assert session.is_empty() is False

    def test_session_clear(self):
        """Test session clear method"""
        session = Session(self.manager)

        session["key1"] = "value1"
        session["key2"] = "value2"

        session.clear()
        assert session._session_cache == {}
        assert session.deleted is True

    def test_session_get_session_key(self):
        """Test getting session key"""
        session = Session(self.manager, "custom-key")
        assert session.get_session_key() == "custom-key"

        session_no_key = Session(self.manager)
        # Should generate a key
        key = session_no_key.get_session_key()
        assert key is not None

    def test_session_expiration_time(self):
        """Test session expiration time"""
        session = Session(self.manager)

        # Test default expiration
        expiration = session.get_expiration_time()
        assert expiration is not None
        assert isinstance(expiration, datetime)

    def test_session_has_expired(self):
        """Test session has_expired method"""
        session = Session(self.manager)

        # Should not be expired initially
        assert session.has_expired() is False

        # Set expiration to past time
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        session.set_expiration_time(past_time)
        assert session.has_expired() is True

    def test_session_should_set_cookie(self):
        """Test should_set_cookie property"""
        session = Session(self.manager)

        # Initially should not set cookie if not modified
        assert session.should_set_cookie is False

        # After modification, should set cookie
        session["key1"] = "value1"
        assert session.should_set_cookie is True

    def test_session_set_and_get_methods(self):
        """Test set and get methods"""
        session = Session(self.manager)

        session.set("key1", "value1")
        assert session.get("key1") == "value1"
        assert session.modified is True
        assert session.accessed is True

    def test_session_str_method(self):
        """Test session string representation"""
        session = Session(self.manager)

        session["key1"] = "value1"
        str_repr = str(session)
        assert "Session" in str_repr
        assert "key1" in str_repr

    def test_create_session_via_interface(self):
        """Test creating session via interface"""
        manager = MockSessionManager()

        session = manager.create_session("test-key")
        assert isinstance(session, Session)
        assert session.session_key == "test-key"
        assert session.interface is manager

    def test_generate_session_key(self):
        """Test session key generation"""
        manager = MockSessionManager()
        key = manager.generate_session_key()

        assert key is not None
        assert len(key) == 64  # 32 bytes hex = 64 chars


class TestSessionInterfaceCookieConfig:
    """Test cookie configuration from interface"""

    def setup_method(self):
        """Set up test configuration"""
        config = MakeConfig(secret_key="test-secret-key")
        set_config(config)
        self.manager = MockSessionManager()

    def test_get_cookie_name(self):
        """Test getting cookie name"""
        assert self.manager.get_cookie_name() == "session_id"

    def test_get_cookie_domain(self):
        """Test getting cookie domain"""
        assert self.manager.get_cookie_domain() is None

    def test_get_cookie_path(self):
        """Test getting cookie path"""
        assert self.manager.get_cookie_path() == "/"

    def test_get_cookie_httponly(self):
        """Test getting cookie httponly flag"""
        assert self.manager.get_cookie_httponly() is True

    def test_get_cookie_secure(self):
        """Test getting cookie secure flag"""
        assert self.manager.get_cookie_secure() is False

    def test_get_cookie_samesite(self):
        """Test getting cookie samesite"""
        assert self.manager.get_cookie_samesite() == "lax"
