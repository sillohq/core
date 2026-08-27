"""Covers a handful of session-module methods that the broader session test
suite exercises only indirectly or not at all: SessionConfig's unknown-attribute
error and to_dict(), resolve_session_config()'s "neither shape" fallback,
FileSessionManager's path-traversal guard and no-op delete on an invalid key,
Session.set()/__str__, and SignedSessionManager's missing-secret-key guard.
"""

from __future__ import annotations

import tempfile

import pytest

from sillo.session.config import SessionConfig, resolve_session_config
from sillo.session.file import FileSessionManager
from sillo.session.session_objects import Session
from sillo.session.signed_cookies import SignedSessionManager


def test_session_config_unknown_attribute_raises():
    config = SessionConfig()
    with pytest.raises(AttributeError, match="no setting 'not_a_real_setting'"):
        _ = config.not_a_real_setting


def test_session_config_private_attribute_raises():
    config = SessionConfig()
    with pytest.raises(AttributeError):
        _ = config._private_thing


def test_session_config_to_dict():
    config = SessionConfig(session_cookie_name="sid")
    data = config.to_dict()
    assert data["session_cookie_name"] == "sid"


def test_resolve_session_config_returns_none_for_unrelated_object():
    assert resolve_session_config(object()) is None


class _FileConfig:
    def __init__(self, path):
        self.session_file_storage_path = path


async def test_file_manager_delete_key_ignores_invalid_key():
    manager = FileSessionManager(config=_FileConfig(tempfile.mkdtemp()))
    # Should be a silent no-op rather than raising, since an invalid key has
    # no corresponding file to remove.
    await manager.delete_key("../../etc/passwd")


def test_session_set_method():
    class MockManager:
        config = None

    session = Session(MockManager())
    session.set("key1", "value1")
    assert session["key1"] == "value1"
    assert session.modified is True
    assert session.accessed is True


def test_session_str_representation():
    class MockManager:
        config = None

    session = Session(MockManager(), "key")
    session["a"] = 1
    assert str(session) == "<Session {'a': 1}>"


def test_signed_session_manager_requires_secret_key():
    with pytest.raises(RuntimeError, match="secret_key is required"):
        SignedSessionManager(secret_key=None)
