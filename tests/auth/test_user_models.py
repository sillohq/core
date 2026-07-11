"""
User Model Tests

This module tests user models including:
- BaseUser abstract methods
- SimpleUser implementation
- UnauthenticatedUser
"""

import pytest

from sillo.auth.users.base import BaseUser
from sillo.auth.users.simple import SimpleUser, UnauthenticatedUser


def test_simple_user_creation():
    """Test SimpleUser creation and properties."""
    user = SimpleUser("testuser", ["read", "write"])

    assert user.identity == "testuser"
    assert user.display_name == "testuser"
    assert user.is_authenticated is True
    assert user.has_permission("read") is True
    assert user.has_permission("admin") is False


async def test_simple_user_load_user():
    """Test SimpleUser.load_user method."""
    user = await SimpleUser.load_user("test_identity")

    assert user.identity == "test_identity"
    assert user.display_name == "test_identity"
    assert user.is_authenticated is True
    assert user.permissions == ["test_identity"]


def test_unauthenticated_user():
    """Test UnauthenticatedUser properties."""
    user = UnauthenticatedUser()

    assert user.identity == ""
    assert user.display_name == ""
    assert user.is_authenticated is False
    assert user.has_permission("anything") is False


async def test_base_user_abstract_methods():
    """Test that BaseUser abstract methods raise NotImplementedError."""
    user = BaseUser()

    with pytest.raises(NotImplementedError):
        _ = user.display_name

    with pytest.raises(NotImplementedError):
        _ = user.identity

    with pytest.raises(NotImplementedError):
        user.has_permission("test")

    with pytest.raises(NotImplementedError):
        await BaseUser.load_user("test")


def test_simple_user_empty_permissions():
    """Test SimpleUser with empty permissions list."""
    user = SimpleUser("testuser", [])

    assert user.has_permission("read") is False
    assert user.has_permission("write") is False
    assert user.permissions == []


def test_simple_user_permission_checking():
    """Test SimpleUser permission checking logic."""
    user = SimpleUser("testuser", ["read", "write", "admin"])

    assert user.has_permission("read") is True
    assert user.has_permission("write") is True
    assert user.has_permission("admin") is True
    assert user.has_permission("delete") is False
    assert user.has_permission("") is False


async def test_simple_user_load_user_different_identities():
    """Test SimpleUser.load_user with different identities."""
    user1 = await SimpleUser.load_user("user1")
    user2 = await SimpleUser.load_user("user2")

    assert user1.identity == "user1"
    assert user2.identity == "user2"
    assert user1.permissions == ["user1"]
    assert user2.permissions == ["user2"]
