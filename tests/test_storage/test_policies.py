"""Coverage for sillo.storage.policies: each policy's __repr__, and Owned's
area() helper — none of which were exercised elsewhere (the bucket
integration tests only call allows()/signable()).
"""

from __future__ import annotations

import pytest

from sillo.storage.policies import Owned, Private, Public, ReadOnly, Signed


def test_private_repr():
    assert repr(Private()) == "Private()"


def test_public_repr():
    assert repr(Public()) == "Public()"


def test_readonly_repr():
    assert repr(ReadOnly()) == "ReadOnly()"


def test_readonly_signable_only_for_read():
    from sillo.storage.base import Action

    policy = ReadOnly()
    assert policy.signable(Action.READ) is True
    assert policy.signable(Action.WRITE) is False


def test_signed_repr():
    assert repr(Signed()) == "Signed()"


def test_signed_allows_nothing():
    from sillo.storage.base import Action

    class User:
        is_authenticated = True
        identity = "1"

    assert Signed().allows(Action.READ, "key", User()) is False


def test_signed_signable_only_for_read():
    from sillo.storage.base import Action

    policy = Signed()
    assert policy.signable(Action.READ) is True
    assert policy.signable(Action.WRITE) is False


def test_owned_prefix_must_contain_id_placeholder():
    with pytest.raises(ValueError, match=r"\{id\}"):
        Owned("no-placeholder/")


def test_owned_area_returns_the_users_prefix():
    policy = Owned("uploads/{id}/")

    class User:
        is_authenticated = True
        identity = "42"

    assert policy.area(User()) == "uploads/42/"


def test_owned_repr():
    policy = Owned("uploads/{id}/", readable=True)
    assert repr(policy) == "Owned(prefix='uploads/{id}/', readable=True)"
