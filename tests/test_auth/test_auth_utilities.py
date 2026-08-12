"""
Authentication Utility Tests

This module tests authentication utility functions including:
- JWT creation/decoding edge cases
- API key creation and verification
- Session login/logout utilities
"""

import time
from datetime import datetime, timedelta, timezone

import pytest

from sillo.application import SilloApp
from sillo.auth import create_jwt, decode_jwt
from sillo.auth.apikey import create_api_key, verify_key
from sillo.auth.session_auth import login, logout
from sillo.users import SimpleUser
from sillo.session.middleware import SessionMiddleware


def test_create_jwt_basic():
    """Test basic JWT creation."""
    payload = {"user_id": 1, "username": "test"}
    token = create_jwt(payload, "a-test-jwt-secret-key-for-hs256")

    assert isinstance(token, str)
    assert len(token) > 0

    # Verify it can be decoded
    decoded = decode_jwt(token, "a-test-jwt-secret-key-for-hs256")
    assert decoded["user_id"] == 1
    assert decoded["username"] == "test"


def test_create_jwt_with_expiration():
    """Test JWT creation with expiration."""
    payload = {"user_id": 1, "username": "test"}
    expires_in = timedelta(hours=1)
    token = create_jwt(payload, "a-test-jwt-secret-key-for-hs256", expires_in=expires_in)

    decoded = decode_jwt(token, "a-test-jwt-secret-key-for-hs256")
    assert "exp" in decoded

    # Check expiration is approximately correct (within 1 second)
    expected_exp = datetime.now(timezone.utc) + expires_in
    actual_exp = datetime.fromtimestamp(decoded["exp"], timezone.utc)
    assert abs((actual_exp - expected_exp).total_seconds()) < 1


def test_create_jwt_custom_algorithm():
    """Test JWT creation with custom algorithm."""
    payload = {"user_id": 1, "username": "test"}
    token = create_jwt(payload, "a-test-jwt-secret-key-for-hs256", algorithm="HS256")

    decoded = decode_jwt(token, "a-test-jwt-secret-key-for-hs256", ["HS256"])
    assert decoded["user_id"] == 1


def test_decode_jwt_invalid_signature():
    """Test JWT decoding with invalid signature."""
    payload = {"user_id": 1, "username": "test"}
    token = create_jwt(payload, "a-test-jwt-secret-key-for-hs256")

    with pytest.raises(ValueError, match="Invalid token"):
        decode_jwt(token, "wrong_secret")


def test_decode_jwt_expired():
    """Test JWT decoding of expired token."""
    payload = {"user_id": 1, "username": "test", "exp": 1}
    token = create_jwt(payload, "a-test-jwt-secret-key-for-hs256")

    with pytest.raises(ValueError, match="Token has expired"):
        decode_jwt(token, "a-test-jwt-secret-key-for-hs256")


def test_decode_jwt_malformed():
    """Test JWT decoding of malformed token."""
    with pytest.raises(ValueError, match="Invalid token"):
        decode_jwt("not.a.valid.token", "a-test-jwt-secret-key-for-hs256")


def test_create_api_key():
    """Test API key creation."""
    api_key, hashed_key = create_api_key()

    assert isinstance(api_key, str)
    assert isinstance(hashed_key, str)
    assert len(api_key) > 0
    assert len(hashed_key) == 64  # SHA256 hash length
    assert api_key.startswith("key_")


def test_verify_key_valid():
    """Test API key verification with valid key."""
    api_key, hashed_key = create_api_key()

    assert verify_key(api_key, hashed_key) is True


def test_verify_key_invalid():
    """Test API key verification with invalid key."""
    _, hashed_key = create_api_key()
    invalid_key = "key_invalidtoken"

    assert verify_key(invalid_key, hashed_key) is False


def test_verify_key_timing_attack_protection():
    """Test that verify_key uses constant time comparison."""
    api_key, hashed_key = create_api_key()

    # This should take the same amount of time regardless of correctness
    start = time.time()
    verify_key(api_key, hashed_key)  # Correct
    correct_time = time.time() - start

    start = time.time()
    verify_key("wrong", hashed_key)  # Incorrect
    wrong_time = time.time() - start

    # Times should be very close (within 10ms)
    assert abs(correct_time - wrong_time) < 0.01


async def test_session_login_logout():
    """Test session login and logout utilities."""
    app = SilloApp()
    app.use(SessionMiddleware(secret_key="secret"))

    # A real Session, not a bare dict: login() rotates the session identifier,
    # which is something only a Session can do. A dict stood in for one here
    # and went on passing while that rotation did not exist.
    from sillo.session.signed_cookies import SignedSessionManager
    from sillo.session.session_objects import Session

    class MockRequest:
        def __init__(self):
            manager = SignedSessionManager(secret_key="secret")
            self.scope = {"session": Session(manager, "a" * 64)}

        @property
        def session(self):
            return self.scope["session"]

    request = MockRequest()
    user = SimpleUser("test")

    # Test login
    login(request, user)
    assert request.scope["session"]["user"]["id"] == "test"
    assert request.scope["session"]["user"]["display_name"] == "test"
    # The identifier the session arrived with must not have survived it.
    assert request.scope["session"].session_key != "a" * 64

    # Test logout
    logout(request)
    assert "user" not in request.scope["session"]
    assert request.scope["session"].deleted is True


def test_session_login_without_session_middleware():
    """Test session login without session middleware raises error."""
    app = SilloApp()
    app.use(SessionMiddleware(secret_key="secret"))

    # Create a mock request without session
    class MockRequest:
        def __init__(self):
            self.scope = {}

    request = MockRequest()
    user = SimpleUser("test")

    with pytest.raises(AssertionError, match="No Session Middleware Installed"):
        login(request, user)


def test_session_logout_without_session_middleware():
    """Test session logout without session middleware raises error."""
    app = SilloApp()
    app.use(SessionMiddleware(secret_key="secret"))

    # Create a mock request without session
    class MockRequest:
        def __init__(self):
            self.scope = {}

    request = MockRequest()

    with pytest.raises(AssertionError, match="No Session Middleware Installed"):
        logout(request)


def test_create_jwt_with_payload_modification():
    """Test JWT creation preserves payload integrity."""
    original_payload = {"user_id": 123, "role": "admin", "active": True}
    token = create_jwt(original_payload, "a-test-jwt-secret-key-for-hs256", expires_in=timedelta(minutes=10))

    decoded = decode_jwt(token, "a-test-jwt-secret-key-for-hs256")
    assert decoded["user_id"] == 123
    assert decoded["role"] == "admin"
    assert decoded["active"] is True
    assert "exp" in decoded  # Should have expiration added
