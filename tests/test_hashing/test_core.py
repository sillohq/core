"""
Password hashing.

The error paths matter more than the happy one here. A `verify_password` that
raises on a malformed hash rather than returning False turns a corrupted row
into a 500 on the login page, and a `needs_update` that raises turns a routine
rehash into an outage.
"""

from __future__ import annotations

import pytest

from sillo.hashing.core import (
    get_available_schemes_list,
    hash_password,
    is_hashed,
    needs_rehash,
    needs_update,
    set_default_scheme,
    verify_password,
)


class TestHashing:
    def test_a_password_hashes(self):
        assert hash_password("correct horse") != "correct horse"

    def test_the_same_password_hashes_differently_each_time(self):
        """A salt that does not vary is not a salt."""
        assert hash_password("same") != hash_password("same")

    def test_a_hash_verifies_against_its_password(self):
        assert verify_password("correct horse", hash_password("correct horse"))

    def test_a_hash_does_not_verify_against_another(self):
        assert verify_password("wrong", hash_password("correct horse")) is False

    def test_an_empty_password_still_hashes(self):
        assert verify_password("", hash_password(""))

    def test_an_overlong_password_is_refused_rather_than_truncated(self):
        """bcrypt's limit is 72 bytes. Truncating silently would mean a
        different password verifies — `xxxx...` and `xxxx...different` hash
        identically — so raising is the right answer and this pins it."""
        with pytest.raises(ValueError, match="72 bytes"):
            hash_password("x" * 200)

    def test_a_password_at_the_limit_still_works(self):
        at_limit = "x" * 72
        assert verify_password(at_limit, hash_password(at_limit))

    def test_a_unicode_password_round_trips(self):
        assert verify_password("pässwörd·日本", hash_password("pässwörd·日本"))


class TestMalformedInput:
    @pytest.mark.parametrize(
        "value", ["", "not-a-hash", "$", "$unknown$rounds$abc", "x" * 200]
    )
    def test_verifying_against_rubbish_is_false_not_an_exception(self, value):
        """A corrupted row must not become a 500 on the login page."""
        assert verify_password("anything", value) is False

    @pytest.mark.parametrize("value", ["", "not-a-hash", "$nope$"])
    def test_needs_update_of_rubbish_does_not_raise(self, value):
        assert isinstance(needs_update(value), bool)

    @pytest.mark.parametrize("value", ["", "not-a-hash", "$nope$"])
    def test_needs_rehash_of_rubbish_does_not_raise(self, value):
        assert isinstance(needs_rehash(value), bool)


class TestRecognition:
    def test_a_real_hash_is_recognised(self):
        assert is_hashed(hash_password("x")) is True

    @pytest.mark.parametrize(
        "value", ["", "plaintext", "correct horse battery staple", "$", "abc123"]
    )
    def test_a_plain_string_is_not(self, value):
        assert is_hashed(value) is False

    def test_a_fresh_hash_does_not_need_updating(self):
        assert needs_update(hash_password("x")) is False


class TestSchemes:
    def test_at_least_one_scheme_is_available(self):
        """pbkdf2_sha256 is built into passlib, so this holds with nothing
        else installed."""
        assert get_available_schemes_list()

    def test_the_default_can_be_changed(self):
        original = get_available_schemes_list()[0]
        try:
            set_default_scheme(original)
            assert verify_password("x", hash_password("x"))
        finally:
            set_default_scheme(original)

    def test_an_unknown_scheme_is_refused(self):
        with pytest.raises(Exception):
            set_default_scheme("rot13")
