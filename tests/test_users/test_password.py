"""
Password hashing, verification, and strength checking.

bcrypt is an optional dependency, so every test that needs it is skipped
rather than failed when it is absent.
"""

import pytest

from sillo.hashing import (
    constant_time_compare,
    is_password_usable,
    md5,
    needs_rehash,
    password_strength,
    sha256,
    validate_password,
)
from sillo.users import check_password, make_password

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


# ── algorithm selection ──────────────────────────────────────────────────────


def test_default_scheme_is_used_when_not_specified():
    """When no scheme specified, default is used."""
    hashed = make_password("test123")
    # Bcrypt hashes start with $2a$, $2b$, $2x$, or $2y$
    assert hashed.startswith(("$2a$", "$2b$", "$2x$", "$2y$"))


def test_can_explicitly_use_bcrypt_scheme():
    """User can explicitly specify bcrypt algorithm."""
    hashed = make_password("test123", scheme="bcrypt")
    assert hashed.startswith(("$2a$", "$2b$", "$2x$", "$2y$"))
    assert check_password("test123", hashed) is True


def test_can_explicitly_use_pbkdf2_scheme():
    """User can explicitly specify pbkdf2_sha256 (built-in, always available)."""
    hashed = make_password("test123", scheme="pbkdf2_sha256")
    # pbkdf2 hashes start with $pbkdf2-sha256$
    assert hashed.startswith("$pbkdf2-sha256$")
    assert check_password("test123", hashed) is True


def test_pbkdf2_fallback_works():
    """pbkdf2_sha256 is built-in and works even without bcrypt."""
    hashed = make_password("test123", scheme="pbkdf2_sha256")
    assert check_password("test123", hashed) is True
    assert check_password("wrong", hashed) is False


def test_different_schemes_produce_different_hashes():
    """Same password hashed with different schemes produces different hashes."""
    bcrypt_hash = make_password("test123", scheme="bcrypt")
    pbkdf2_hash = make_password("test123", scheme="pbkdf2_sha256")

    # Hashes should be different
    assert bcrypt_hash != pbkdf2_hash
    # But both should verify the same password
    assert check_password("test123", bcrypt_hash) is True
    assert check_password("test123", pbkdf2_hash) is True


def test_can_mix_schemes_in_same_app():
    """App can have users with different hashing schemes and verify them all."""
    password = "mysecretpassword"

    bcrypt_hash = make_password(password, scheme="bcrypt")
    pbkdf2_hash = make_password(password, scheme="pbkdf2_sha256")

    # Both schemes should verify the password
    assert check_password(password, bcrypt_hash) is True
    assert check_password(password, pbkdf2_hash) is True

    # Wrong password fails on both
    assert check_password("wrongpassword", bcrypt_hash) is False
    assert check_password("wrongpassword", pbkdf2_hash) is False


def test_explicit_scheme_with_rounds():
    """Can pass additional parameters like rounds to the hash function."""
    # For bcrypt, rounds is passed via salt parameter
    salt = bcrypt.gensalt(rounds=4)
    hashed = make_password("test123", salt=salt.decode())
    assert check_password("test123", hashed) is True


# Check if argon2 is available for optional tests
argon2_available = False
try:
    from sillo.hashing.config import is_scheme_available
    argon2_available = is_scheme_available("argon2")
except ImportError:
    pass


@pytest.mark.skipif(not argon2_available, reason="argon2 not available in passlib")
def test_can_use_argon2_scheme():
    """When argon2-cffi is installed and available, user can specify argon2 scheme."""
    hashed = make_password("test123", scheme="argon2")
    # Argon2 hashes contain argon2 identifier
    assert "argon2" in hashed.lower()
    assert check_password("test123", hashed) is True


# Check if scrypt is available for optional tests
scrypt_available = False
try:
    import scrypt
    scrypt_available = True
except ImportError:
    pass


@pytest.mark.skipif(not scrypt_available, reason="scrypt not installed")
def test_can_use_scrypt_scheme():
    """When scrypt is installed, user can specify scrypt scheme."""
    hashed = make_password("test123", scheme="scrypt")
    # Scrypt hashes contain scrypt identifier
    assert "scrypt" in hashed
    assert check_password("test123", hashed) is True
