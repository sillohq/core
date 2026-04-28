"""
Tests for signed cookie session manager
"""

import pytest

from nexios.config import MakeConfig, set_config
from nexios.session.base import BaseSessionInterface
from nexios.session.session_objects import Session
from nexios.session.signed_cookies import SignedSessionManager


class TestSignedSessionManager:
    """Test signed cookie session manager functionality"""

    def setup_method(self):
        """Set up test configuration"""
        self.manager = SignedSessionManager(
            secret_key="test-secret-key-for-signed-sessions"
        )

    def test_signed_session_initialization(self):
        """Test signed session manager initialization"""
        manager = SignedSessionManager(secret_key="test-secret-key")
        assert manager.serializer is not None

    def test_sign_and_verify_session_data(self):
        """Test signing and verifying session data"""
        manager = SignedSessionManager(secret_key="test-secret-key")

        test_data = {"user_id": 123, "preferences": {"theme": "dark"}}
        signed_token = manager.sign_session_data(test_data)

        assert isinstance(signed_token, str)
        assert signed_token != ""

        verified_data = manager.verify_session_data(signed_token)
        assert verified_data == test_data

    def test_verify_invalid_signature(self):
        """Test verification of invalid signature"""
        manager = SignedSessionManager(secret_key="test-secret-key")

        invalid_token = "invalid.signature.here"
        verified_data = manager.verify_session_data(invalid_token)

        assert verified_data == {}

    def test_verify_empty_token(self):
        """Test verification of empty token"""
        manager = SignedSessionManager(secret_key="test-secret-key")

        verified_data = manager.verify_session_data("")
        assert verified_data == {}

        verified_data = manager.verify_session_data(None)
        assert verified_data == {}

    async def test_async_save(self):
        """Test async save method"""
        manager = SignedSessionManager(secret_key="test-secret-key")
        session = manager.create_session()

        session["user_id"] = 789
        session["settings"] = {"notifications": True}

        signed_session = await session.save()
        assert isinstance(signed_session, str)
        assert signed_session != ""

        assert session.session_key == signed_session

    async def test_async_load(self):
        """Test async load method"""
        manager = SignedSessionManager(secret_key="test-secret-key")

        test_data = {"user_id": 101, "logged_in": True}
        signed_token = manager.sign_session_data(test_data)

        session = manager.create_session(signed_token)
        await session.load()
        assert session._session_cache == test_data

        empty_session = manager.create_session()
        await empty_session.load()
        assert empty_session._session_cache == {}

    async def test_session_operations_with_signed_cookies(self):
        """Test full session operations with signed cookies"""
        manager = SignedSessionManager(secret_key="test-secret-key")
        session = manager.create_session()

        session["user_id"] = 202
        session["cart"] = ["item1", "item2"]

        await session.save()

        new_session = manager.create_session(session.session_key)
        await new_session.load()

        assert new_session["user_id"] == 202
        assert new_session["cart"] == ["item1", "item2"]

    def test_clear_session(self):
        """Test clearing session data"""
        manager = SignedSessionManager(secret_key="test-secret-key")
        session = manager.create_session()

        session["user_id"] = 303
        session["data"] = "test"

        session.clear()
        assert session._session_cache == {}

    async def test_session_key_generation(self):
        """Test session key generation"""
        manager = SignedSessionManager(secret_key="test-secret-key")
        session = manager.create_session()

        assert session.session_key is None

        session["test"] = "value"
        await session.save()

        assert session.session_key is not None
        assert isinstance(session.session_key, str)

    async def test_multiple_save_load_cycles(self):
        """Test multiple save and load cycles"""
        manager = SignedSessionManager(secret_key="test-secret-key")
        session = manager.create_session()

        session["counter"] = 1
        await session.save()
        key1 = session.session_key

        session["counter"] = 2
        await session.save()
        key2 = session.session_key

        assert key1 != key2

        new_session = manager.create_session(key2)
        await new_session.load()
        assert new_session["counter"] == 2

    async def test_session_with_complex_data(self):
        """Test session with complex data types"""
        manager = SignedSessionManager(secret_key="test-secret-key")
        session = manager.create_session()

        complex_data = {
            "user": {
                "id": 404,
                "profile": {
                    "name": "Test User",
                    "preferences": {"theme": "light", "notifications": True},
                },
            },
            "items": [1, 2, 3],
            "active": True,
        }

        session["complex"] = complex_data
        await session.save()

        new_session = manager.create_session(session.session_key)
        await new_session.load()

        assert new_session["complex"] == complex_data

    def test_signed_manager_creates_session(self):
        """Test that manager creates proper Session objects"""
        manager = SignedSessionManager(secret_key="test-secret-key")
        session = manager.create_session("test-key")

        assert isinstance(session, Session)
        assert session.session_key == "test-key"
        assert session.interface is manager
