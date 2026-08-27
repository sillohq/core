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

    def test_hash_password_accepts_an_explicit_bcrypt_salt(self):
        import bcrypt as bcrypt_lib

        salt = bcrypt_lib.gensalt(rounds=12)
        hashed = hash_password("x", scheme="bcrypt", salt=salt)
        assert verify_password("x", hashed)

    def test_hash_password_accepts_an_explicit_bcrypt_salt_as_str(self):
        import bcrypt as bcrypt_lib

        salt = bcrypt_lib.gensalt(rounds=12).decode()
        hashed = hash_password("x", scheme="bcrypt", salt=salt)
        assert verify_password("x", hashed)


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

    def test_hash_password_with_unavailable_scheme_raises(self):
        from sillo.hashing.exceptions import InvalidSchemeError

        with pytest.raises(InvalidSchemeError):
            hash_password("x", scheme="not-a-real-scheme")

    def test_hash_password_wraps_unexpected_backend_errors(self, monkeypatch):
        import sillo.hashing.core as core

        class ExplodingContext:
            def hash(self, *args, **kwargs):
                raise RuntimeError("backend exploded")

        monkeypatch.setattr(core, "_get_context", lambda: ExplodingContext())

        with pytest.raises(core.HashingError, match="Failed to hash password"):
            hash_password("x", scheme="pbkdf2_sha256")

    def test_get_context_raises_when_no_schemes_available(self, monkeypatch):
        import sillo.hashing.core as core

        monkeypatch.setattr(core, "_context", None)
        monkeypatch.setattr(core, "get_available_schemes", lambda: [])

        with pytest.raises(core.HashingError, match="No hashing schemes available"):
            core._get_context()

    def test_verify_password_with_malformed_bcrypt_prefixed_hash(self):
        assert verify_password("x", "$2b$not-actually-bcrypt") is False

    @pytest.mark.parametrize("value", ["$2", "$2b", "$2b$notarounds$rest"])
    def test_needs_update_with_incomplete_bcrypt_hash_says_yes(self, value):
        assert needs_update(value) is True

    @pytest.mark.parametrize("value", ["$2", "$2b", "$2b$notarounds$rest"])
    def test_needs_rehash_with_incomplete_bcrypt_hash_says_yes(self, value):
        assert needs_rehash(value) is True

    def test_needs_rehash_compares_against_a_well_formed_bcrypt_hash(self):
        # rounds=12 in the hash itself, so needs_update() (fixed threshold 12)
        # says no update is needed — needs_rehash()'s own rounds comparison
        # is what actually gets exercised here.
        hashed = hash_password("x", scheme="bcrypt")
        assert needs_rehash(hashed, rounds=12) is False
        assert needs_rehash(hashed, rounds=14) is True

    def test_is_hashed_falls_back_to_prefix_check_without_passlib(self, monkeypatch):
        import sillo.hashing.core as core

        def _raise():
            raise core.HashingError("no passlib")

        monkeypatch.setattr(core, "_get_context", _raise)

        assert is_hashed("$argon2$something") is True
        assert is_hashed("plainly not a hash") is False
