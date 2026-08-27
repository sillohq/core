"""
Digests, HMAC, and symmetric encryption helpers.

``cryptography`` is optional, so the encryption tests skip when it is absent.
The digest and signing helpers have no optional dependency.
"""

import base64

import pytest

from sillo.helpers.hashing import (
    constant_time_compare,
    digest,
    hash_file,
    hmac_digest,
    md5,
    random_salt,
    sha1,
    sha256,
    sha512,
)


# ── digests ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fn,length", [(md5, 32), (sha1, 40), (sha256, 64), (sha512, 128)]
)
def test_digest_lengths(fn, length):
    assert len(fn("hello")) == length


@pytest.mark.parametrize("fn", [md5, sha1, sha256, sha512])
def test_digests_are_stable(fn):
    assert fn("hello") == fn("hello")


@pytest.mark.parametrize("fn", [md5, sha1, sha256, sha512])
def test_digests_accept_bytes(fn):
    assert fn(b"hello") == fn("hello")


@pytest.mark.parametrize("fn", [md5, sha1, sha256, sha512])
def test_different_inputs_differ(fn):
    assert fn("a") != fn("b")


def test_digest_defaults_to_sha256():
    assert digest("hello") == sha256("hello")


@pytest.mark.parametrize("algorithm", ["md5", "sha1", "sha256", "sha512"])
def test_digest_by_name(algorithm):
    assert isinstance(digest("hello", algorithm=algorithm), str)


def test_digest_rejects_an_unknown_algorithm():
    with pytest.raises(Exception):
        digest("hello", algorithm="not-a-real-algorithm")


def test_digest_of_an_empty_input():
    assert len(digest("")) == 64


# ── HMAC ─────────────────────────────────────────────────────────────────


def test_hmac_is_stable():
    assert hmac_digest("key", "data") == hmac_digest("key", "data")


def test_hmac_depends_on_the_key():
    assert hmac_digest("key-a", "data") != hmac_digest("key-b", "data")


def test_hmac_depends_on_the_data():
    assert hmac_digest("key", "a") != hmac_digest("key", "b")


def test_hmac_accepts_bytes():
    assert hmac_digest(b"key", b"data") == hmac_digest("key", "data")


def test_hmac_with_another_algorithm():
    assert len(hmac_digest("key", "data", algorithm="sha512")) == 128


def test_hmac_differs_from_a_plain_digest():
    """An unkeyed digest offers no authentication; they must not coincide."""
    assert hmac_digest("key", "data") != sha256("data")


# ── constant time comparison ─────────────────────────────────────────────


def test_constant_time_compare_matches():
    assert constant_time_compare("secret", "secret") is True


def test_constant_time_compare_differs():
    assert constant_time_compare("secret", "s3cret") is False


def test_constant_time_compare_on_different_lengths():
    assert constant_time_compare("a", "abcdef") is False


def test_constant_time_compare_of_empty_strings():
    assert constant_time_compare("", "") is True


# ── salts ────────────────────────────────────────────────────────────────


def test_random_salt_has_the_requested_length():
    assert len(random_salt(16)) >= 16


def test_salts_are_unique():
    assert len({random_salt() for _ in range(50)}) == 50


def test_random_salt_with_a_custom_length():
    assert len(random_salt(32)) >= 32


# ── file hashing ─────────────────────────────────────────────────────────


def test_hash_file(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    assert hash_file(str(f)) == sha256("hello")


def test_hash_file_of_an_empty_file(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_bytes(b"")
    assert hash_file(str(f)) == sha256("")


def test_hash_file_is_chunk_size_independent(tmp_path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"x" * 200_000)
    assert hash_file(str(f), chunk_size=1024) == hash_file(str(f), chunk_size=65536)


def test_hash_file_with_another_algorithm(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    assert hash_file(str(f), algorithm="md5") == md5("hello")


def test_hash_file_of_a_missing_path():
    with pytest.raises(OSError):
        hash_file("/nonexistent/path/nope.txt")


# ── signing and encryption ───────────────────────────────────────────────


class TestSigning:
    """sign_value / unsign_value need no optional dependency."""

    def test_round_trip(self):
        from sillo.helpers.crypto import sign_value, unsign_value

        signed = sign_value("payload", "secret")
        assert unsign_value(signed, "secret") == "payload"

    def test_the_signed_form_is_value_and_signature(self):
        """The value is base64-encoded, so it is not literally present."""
        from sillo.helpers.crypto import sign_value

        signed = sign_value("payload", "secret")
        assert signed.count(".") == 1

    def test_a_wrong_secret_is_rejected(self):
        from sillo.helpers.crypto import sign_value, unsign_value

        signed = sign_value("payload", "secret")
        with pytest.raises(Exception):
            unsign_value(signed, "the-wrong-secret")

    def test_a_tampered_value_is_rejected(self):
        from sillo.helpers.crypto import sign_value, unsign_value

        encoded, signature = sign_value("payload", "secret").split(".")
        forged = base64.urlsafe_b64encode(b"tampered").decode().rstrip("=")
        with pytest.raises(Exception):
            unsign_value(f"{forged}.{signature}", "secret")

    def test_garbage_is_rejected(self):
        from sillo.helpers.crypto import unsign_value

        with pytest.raises(Exception):
            unsign_value("not-signed-at-all", "secret")

    def test_sign_value_accepts_bytes_secret_and_value(self):
        from sillo.helpers.crypto import sign_value, unsign_value

        signed = sign_value(b"payload", b"secret")
        assert unsign_value(signed, b"secret") == "payload"

    def test_unsign_value_max_age_is_not_supported(self):
        from sillo.helpers.crypto import sign_value, unsign_value

        signed = sign_value("payload", "secret")
        with pytest.raises(NotImplementedError, match="max_age"):
            unsign_value(signed, "secret", max_age=60)


class TestEncryption:
    """Symmetric encryption requires the optional cryptography package."""

    @pytest.fixture(autouse=True)
    def _require_cryptography(self):
        pytest.importorskip(
            "cryptography", reason="cryptography is an optional dependency"
        )

    def test_round_trip(self):
        from sillo.helpers.crypto import decrypt, encrypt, generate_key

        key = generate_key()
        assert decrypt(encrypt("secret message", key), key) == "secret message"

    def test_the_ciphertext_hides_the_plaintext(self):
        from sillo.helpers.crypto import encrypt, generate_key

        assert "secret message" not in encrypt("secret message", generate_key())

    def test_the_wrong_key_cannot_decrypt(self):
        from sillo.helpers.crypto import decrypt, encrypt, generate_key

        token = encrypt("secret", generate_key())
        with pytest.raises(Exception):
            decrypt(token, generate_key())

    def test_keys_are_unique(self):
        from sillo.helpers.crypto import generate_key

        assert len({generate_key() for _ in range(10)}) == 10

    def test_derive_key_is_deterministic_for_a_given_salt(self):
        """derive_key returns (key, salt); the same inputs must give the same key."""
        from sillo.helpers.crypto import derive_key

        salt = b"a-fixed-salt-value"
        first_key, first_salt = derive_key("password", salt=salt)
        second_key, _ = derive_key("password", salt=salt)
        assert first_key == second_key
        assert first_salt == salt

    def test_derive_key_generates_a_salt_when_none_is_given(self):
        from sillo.helpers.crypto import derive_key

        _, salt_a = derive_key("password")
        _, salt_b = derive_key("password")
        assert salt_a != salt_b

    def test_derive_key_depends_on_the_password(self):
        from sillo.helpers.crypto import derive_key

        salt = b"a-fixed-salt-value"
        key_a, _ = derive_key("password-a", salt=salt)
        key_b, _ = derive_key("password-b", salt=salt)
        assert key_a != key_b

    def test_ensure_crypto_raises_import_error_without_cryptography(self, monkeypatch):
        import sillo.helpers.crypto as crypto_helpers

        monkeypatch.setattr(crypto_helpers, "_crypto_available", False)
        with pytest.raises(ImportError, match="cryptography is required"):
            crypto_helpers._ensure_crypto()

    def test_unicode_survives_encryption(self):
        from sillo.helpers.crypto import decrypt, encrypt, generate_key

        key = generate_key()
        message = "héllo 日本語 🔒"
        assert decrypt(encrypt(message, key), key) == message
