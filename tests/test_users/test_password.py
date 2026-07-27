"""
Password hashing, verification, and strength checking.

bcrypt is an optional dependency, so every test that needs it is skipped
rather than failed when it is absent.
"""

import pytest

from sillo.users.password import (
    check_password,
    constant_time_compare,
    is_password_usable,
    make_password,
    md5,
    needs_rehash,
    password_strength,
    sha256,
    validate_password,
)

bcrypt = pytest.importorskip("bcrypt", reason="bcrypt is an optional dependency")


# ── hashing ──────────────────────────────────────────────────────────────


def test_hash_is_not_the_plaintext():
    assert make_password("hunter22") != "hunter22"


def test_hash_verifies():
    assert check_password("hunter22", make_password("hunter22")) is True


def test_a_wrong_password_is_rejected():
    assert check_password("wrong", make_password("hunter22")) is False


def test_hashes_are_salted():
    """Two hashes of the same password must differ, or they are rainbow-tableable."""
    assert make_password("same") != make_password("same")


def test_both_salted_hashes_still_verify():
    pw = "same"
    assert check_password(pw, make_password(pw))
    assert check_password(pw, make_password(pw))


def test_an_explicit_salt_is_honoured():
    salt = bcrypt.gensalt(rounds=4).decode()
    assert check_password("pw", make_password("pw", salt=salt)) is True


def test_unicode_passwords():
    pw = "pàsswörd-日本語-🔒"
    assert check_password(pw, make_password(pw)) is True


def test_a_password_over_bcrypt_s_limit_is_rejected():
    """bcrypt caps input at 72 bytes and refuses rather than silently truncating.

    Applications accepting long passphrases must truncate or pre-hash; this
    surfaces as a ValueError, not a silent weakening.
    """
    with pytest.raises(ValueError):
        make_password("x" * 200)


def test_a_password_at_the_limit_is_accepted():
    pw = "x" * 72
    assert check_password(pw, make_password(pw)) is True


def test_an_empty_password_never_authenticates():
    """Hashing an empty string succeeds, but it must not verify — a blank
    password should never grant access to an account."""
    encoded = make_password("")
    assert encoded
    assert check_password("", encoded) is False


# ── malformed input ──────────────────────────────────────────────────────


def test_check_against_a_malformed_hash_is_false_not_an_error():
    assert check_password("pw", "not-a-hash") is False


def test_check_against_an_empty_hash():
    assert check_password("pw", "") is False


def test_usable_hash_detection():
    assert is_password_usable(make_password("pw")) is True


@pytest.mark.parametrize("bad", ["", "!", "!unusable"])
def test_unusable_hashes(bad):
    """Empty, or carrying the explicit unusable marker."""
    assert is_password_usable(bad) is False


def test_usable_only_means_not_explicitly_disabled():
    """It is a marker check, not hash validation — an arbitrary string passes."""
    assert is_password_usable("plaintext") is True


# ── rehashing ────────────────────────────────────────────────────────────


def test_a_weak_hash_needs_rehashing():
    weak = make_password("pw", salt=bcrypt.gensalt(rounds=4).decode())
    assert needs_rehash(weak, rounds=12) is True


def test_a_current_hash_does_not_need_rehashing():
    current = make_password("pw", salt=bcrypt.gensalt(rounds=12).decode())
    assert needs_rehash(current, rounds=12) is False


def test_needs_rehash_on_garbage_does_not_raise():
    assert isinstance(needs_rehash("garbage"), bool)


# ── validation ───────────────────────────────────────────────────────────


def test_a_strong_password_produces_no_complaints():
    assert validate_password("Str0ng!Passphrase") == []


def test_a_short_password_is_rejected():
    assert validate_password("ab") != []


def test_the_minimum_length_is_configurable():
    assert validate_password("abcdefgh", min_length=20) != []


def test_validation_returns_readable_messages():
    errors = validate_password("a")
    assert all(isinstance(e, str) for e in errors)


def test_a_password_similar_to_the_user_is_rejected():
    class User:
        username = "adalovelace"
        email = "ada@example.com"

    assert validate_password("adalovelace", user=User()) != []


# ── strength ─────────────────────────────────────────────────────────────


def test_strength_returns_a_report():
    assert isinstance(password_strength("Str0ng!Passphrase"), dict)


def test_a_stronger_password_scores_higher():
    weak = password_strength("abc")
    strong = password_strength("V3ry!Long&Complex#Passphrase")
    assert strong["score"] > weak["score"]


def test_strength_of_an_empty_password():
    assert isinstance(password_strength(""), dict)


# ── digests and comparison ───────────────────────────────────────────────


def test_constant_time_compare_matches():
    assert constant_time_compare("secret", "secret") is True


def test_constant_time_compare_differs():
    assert constant_time_compare("secret", "s3cret") is False


def test_constant_time_compare_on_different_lengths():
    assert constant_time_compare("a", "abc") is False


def test_md5_is_stable():
    assert md5("hello") == md5("hello")
    assert len(md5("hello")) == 32


def test_md5_accepts_bytes():
    assert md5(b"hello") == md5("hello")


def test_sha256_is_stable():
    assert sha256("hello") == sha256("hello")
    assert len(sha256("hello")) == 64


def test_sha256_accepts_bytes():
    assert sha256(b"hello") == sha256("hello")


def test_different_inputs_give_different_digests():
    assert sha256("a") != sha256("b")
