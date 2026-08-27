"""Direct coverage for sillo.users.protocol: the unusable-password marker,
UserProtocol's default (mostly NotImplementedError) contract methods via a
minimal concrete subclass, and the AnonymousUser methods the existing
test_user_model.py tests don't reach.
"""

from __future__ import annotations

import pytest

from sillo.users.protocol import AnonymousUser, UserProtocol, make_password


def test_make_password_none_returns_unusable_marker():
    from sillo.hashing import UNUSABLE_PASSWORD_PREFIX

    marker = make_password(None)
    assert marker.startswith(UNUSABLE_PASSWORD_PREFIX)


def test_check_password_rejects_malformed_hash():
    from sillo.users.protocol import check_password

    # A hash with a real-looking (non-"unusable") prefix but garbage payload
    # should be treated as invalid rather than raising.
    assert check_password("pw", "bcrypt$$$not-actually-valid") is False


class _ConcreteUser(UserProtocol):
    def __init__(self, uid: str):
        self._id = uid

    @property
    def identity(self) -> str:
        return self._id

    @property
    def display_name(self) -> str:
        return f"user-{self._id}"


def test_is_authenticated_and_is_anonymous_defaults():
    user = _ConcreteUser("1")
    assert user.is_authenticated is True
    assert user.is_anonymous is False


def test_get_id_and_get_display_name():
    user = _ConcreteUser("42")
    assert user.get_id() == "42"
    assert user.get_display_name() == "user-42"


def test_has_perm_defaults_false_and_has_perms_all():
    user = _ConcreteUser("1")
    assert user.has_perm("anything") is False
    assert user.has_perms(["a", "b"]) is False


def test_has_permission_raises_not_implemented():
    user = _ConcreteUser("1")
    with pytest.raises(NotImplementedError):
        user.has_permission("edit")


def test_has_module_perms_uses_is_active_and_is_staff():
    user = _ConcreteUser("1")
    user.is_staff = True
    assert user.has_module_perms("app") is True
    user.is_active = False
    assert user.has_module_perms("app") is False


def test_str_and_repr():
    user = _ConcreteUser("7")
    assert str(user) == "user-7"
    assert repr(user) == "<_ConcreteUser: user-7>"


def test_eq_and_hash():
    a = _ConcreteUser("1")
    b = _ConcreteUser("1")
    c = _ConcreteUser("2")
    assert a == b
    assert a != c
    assert a.__eq__(object()) is NotImplemented
    assert hash(a) == hash(b)


async def test_load_user_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await UserProtocol.load_user("1")


def test_get_email_field_name_default():
    assert UserProtocol.get_email_field_name() == "email"


def test_display_name_and_identity_raise_by_default():
    class _BareUser(UserProtocol):
        pass

    user = _BareUser()
    with pytest.raises(NotImplementedError):
        _ = user.display_name
    with pytest.raises(NotImplementedError):
        _ = user.identity


def test_anonymous_user_has_perms_and_module_perms():
    anon = AnonymousUser()
    assert anon.has_perms(["any"]) is False
    assert anon.has_module_perms("app") is False


def test_anonymous_user_str():
    assert str(AnonymousUser()) == "AnonymousUser"


def test_anonymous_user_get_display_name():
    assert AnonymousUser().get_display_name() == ""


def test_anonymous_user_not_equal_to_other_types():
    assert AnonymousUser().__eq__(object()) is NotImplemented
