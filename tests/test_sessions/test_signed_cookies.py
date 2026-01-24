"""
Tests for signed cookie session manager
"""

import json

import pytest

from nexios.config import MakeConfig,  set_config
from nexios.session.signed_cookies import SignedSessionManager
from nexios.session import SessionConfig

class TestSignedSessionManager:
    """Test signed cookie session manager functionality"""

    def setup_method(self):
        """Set up test configuration"""
        config = MakeConfig(
            secret_key="test-secret-key-for-signed-sessions",
            session=SessionConfig(
                session_cookie_name="test_session",
                session_expiration_time=3600,
                session_permanent=False,
                session_refresh_each_request=False,
            ),
        )
        set_config(config)

    def test_signed_session_initialization(self):
        """Test signed session manager initialization"""
        session = SignedSessionManager("test-session-key")

        assert session.session_key == "test-session-key"
        assert session._session_cache == {}
        assert session.secret_key == "test-secret-key-for-signed-sessions"
        assert session.serializer is not None

    def test_sign_and_verify_session_data(self):
        """Test signing and verifying session data"""
        session = SignedSessionManager()

        test_data = {"user_id": 123, "preferences": {"theme": "dark"}}
        signed_token = session.sign_session_data(test_data)

        assert isinstance(signed_token, str)
        assert signed_token != ""

        # Verify the signed data
        verified_data = session.verify_session_data(signed_token)
        assert verified_data == test_data

    def test_verify_invalid_signature(self):
        """Test verification of invalid signature"""
        session = SignedSessionManager()

        # Invalid token
        invalid_token = "invalid.signature.here"
        verified_data = session.verify_session_data(invalid_token)

        assert verified_data == {}

    def test_verify_empty_token(self):
        """Test verification of empty token"""
        session = SignedSessionManager()

        verified_data = session.verify_session_data("")
        assert verified_data == {}

        verified_data = session.verify_session_data(None)
        assert verified_data == {}

    def test_get_session_cookie(self):
        """Test getting session cookie"""
        session = SignedSessionManager()

        session["user_id"] = 123
        session["username"] = "testuser"

        cookie = session.get_session_cookie()
        assert isinstance(cookie, str)
        assert cookie != ""

        # Verify the cookie can be deserialized
        verified_data = session.verify_session_data(cookie)
        assert verified_data == {"user_id": 123, "username": "testuser"}

    async def test_async_save(self):
        """Test async save method"""
        session = SignedSessionManager()

        session["user_id"] = 789
        session["settings"] = {"notifications": True}

        signed_session = await session.save()
        assert isinstance(signed_session, str)
        assert signed_session != ""

        # The session_key should now be the signed token
        assert session.session_key == signed_session

    async def test_async_load(self):
        """Test async load method"""
        session = SignedSessionManager()

        # Create and save test data
        test_data = {"user_id": 101, "logged_in": True}
        signed_token = session.sign_session_data(test_data)
        session.session_key = signed_token

        # Load the session
        await session.load()
        assert session._session_cache == test_data

        # Test loading with no key
        empty_session = SignedSessionManager()
        await empty_session.load()
        assert empty_session._session_cache == {}

    async def test_session_operations_with_signed_cookies(self):
        """Test full session operations with signed cookies"""
        session = SignedSessionManager()

        # Set some data
        session["user_id"] = 202
        session["cart"] = ["item1", "item2"]

        # Save the session
        await session.save()

        # Create a new session instance and load from the saved key
        new_session = SignedSessionManager(session.session_key)
        await new_session.load()

        # Verify data is preserved
        assert new_session["user_id"] == 202
        assert new_session["cart"] == ["item1", "item2"]

    def test_clear_session(self):
        """Test clearing session data"""
        session = SignedSessionManager()

        session["user_id"] = 303
        session["data"] = "test"

        session.clear()
        assert session._session_cache == {}

    async def test_session_key_generation(self):
        """Test session key generation"""
        session = SignedSessionManager()

        # Initially no key
        assert session.session_key is None

        # After save, should have a key
        session["test"] = "value"
        await session.save()

        assert session.session_key is not None
        assert isinstance(session.session_key, str)

    async def test_multiple_save_load_cycles(self):
        """Test multiple save and load cycles"""
        session = SignedSessionManager(
            session_key="test-session-key-for-multiple-save-load-cycles"
        )

        # First cycle
        session["counter"] = 1
        await session.save()
        key1 = session.session_key

        # Second cycle with new data
        session["counter"] = 2
        await session.save()
        key2 = session.session_key

        # Keys should be different since data changed
        assert key1 != key2

        # Load from second key
        new_session = SignedSessionManager(key2)
        await new_session.load()
        assert new_session["counter"] == 2

    async def test_session_with_complex_data(self):
        """Test session with complex data types"""
        session = SignedSessionManager(session_key="test-session-key-for-complex-data")

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

        # Load in new session
        new_session = SignedSessionManager(session.session_key)
        await new_session.load()

        assert new_session["complex"] == complex_data
