"""
The security properties, each asserted so that it can fail.

A test that cannot fail is not a test. For every refusal here there is a
companion showing the same input is accepted once the protection is removed, so
the assertion is measuring the guard rather than an accident of the fixture.
"""

from __future__ import annotations

import time

import pytest

from sillo.storage.errors import SignatureInvalid, UnsafeKey
from sillo.storage.paths import contain, normalise
from sillo.storage.signing import SignedGrant, Signer
from sillo.storage.sniff import sniff


class TestKeys:
    @pytest.mark.parametrize(
        "key",
        [
            "../etc/passwd",
            "a/../../etc/passwd",
            "/etc/passwd",
            "..",
            "a/b/../../..",
            "a\\b",
            "a\x00b",
            "a\nb",
            "",
            "   ",
        ],
    )
    def test_an_unsafe_key_is_refused(self, key):
        with pytest.raises(UnsafeKey):
            normalise(key)

    @pytest.mark.parametrize(
        "key,expected",
        [
            ("a/b.txt", "a/b.txt"),
            ("./a/b.txt", "a/b.txt"),
            ("a//b.txt", "a/b.txt"),
            ("a/./b.txt", "a/b.txt"),
            ("a/c/../b.txt", "a/b.txt"),
        ],
    )
    def test_a_safe_key_normalises(self, key, expected):
        assert normalise(key) == expected

    def test_two_spellings_of_one_name_are_one_key(self):
        """Without NFC a macOS upload and a Linux upload of the same filename
        are two objects that look identical in every listing."""
        assert normalise("café.pdf") == normalise("café.pdf")

    def test_a_key_that_is_too_long_is_refused(self):
        with pytest.raises(UnsafeKey):
            normalise("a" * 2000)

    def test_a_segment_that_is_too_long_is_refused(self):
        with pytest.raises(UnsafeKey):
            normalise(f"a/{'b' * 300}/c.txt")

    def test_containment_is_by_resolution(self, tmp_path):
        """Not by looking for `..` in the input, which misses encodings,
        symlinks, and whatever is invented next."""
        outside = tmp_path / "outside"
        outside.mkdir()
        root = tmp_path / "bucket"
        root.mkdir()

        (root / "escape").symlink_to(outside)

        with pytest.raises(UnsafeKey):
            contain(root, "escape/secrets.txt")

    def test_containment_permits_what_is_inside(self, tmp_path):
        assert contain(tmp_path, "a/b.txt").is_relative_to(tmp_path.resolve())


class TestSniffing:
    def test_html_declared_as_an_image_is_stored_as_html(self):
        """The shape of a stored cross-site scripting attempt: bytes that are
        markup, a declared type that says otherwise."""
        assert (
            sniff(b"<!DOCTYPE html><script>alert(1)</script>", declared="image/png")
            == "text/html"
        )

    def test_the_declared_type_cannot_promote_a_binary(self):
        assert sniff(b"\x00\x01\x02\x03", declared="image/png") == "application/octet-stream"

    def test_a_real_image_is_an_image(self):
        assert sniff(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32) == "image/png"

    def test_svg_is_recognised_as_svg(self):
        """It renders and it can carry script, so it must not become text."""
        assert sniff(b'<svg xmlns="http://www.w3.org/2000/svg"/>') == "image/svg+xml"

    def test_a_bare_script_tag_is_html(self):
        assert sniff(b"<script>alert(1)</script>", declared="text/plain") == "text/html"

    def test_an_unknown_binary_downloads_rather_than_renders(self):
        assert sniff(b"\xde\xad\xbe\xef" * 20) == "application/octet-stream"

    def test_an_empty_file_is_not_guessed_at(self):
        assert sniff(b"") == "application/octet-stream"

    def test_the_declared_type_only_breaks_ties_between_textual_types(self):
        assert sniff(b"name,email\na,b", declared="text/csv") == "text/csv"
        assert sniff(b"name,email\na,b", declared="text/html") == "text/plain"


class TestSigning:
    @pytest.fixture
    def signer(self):
        return Signer("a-secret-that-is-long-enough", "avatars")

    def test_a_fresh_token_verifies(self, signer):
        grant = SignedGrant("a.png", "GET", time.time() + 300)
        assert signer.verify(signer.sign(grant), key="a.png", method="GET")

    def test_an_expired_token_is_refused(self, signer):
        token = signer.sign(SignedGrant("a.png", "GET", time.time() - 1))
        with pytest.raises(SignatureInvalid):
            signer.verify(token, key="a.png", method="GET")

    def test_a_token_would_verify_if_it_had_not_expired(self, signer):
        """Proving the previous test measures expiry and not something else."""
        token = signer.sign(SignedGrant("a.png", "GET", time.time() + 300))
        assert signer.verify(token, key="a.png", method="GET")

    def test_a_tampered_token_is_refused(self, signer):
        token = signer.sign(SignedGrant("a.png", "GET", time.time() + 300))
        with pytest.raises(SignatureInvalid):
            signer.verify(token[:-4] + "AAAA", key="a.png", method="GET")

    def test_a_read_token_cannot_write(self, signer):
        """A signature over the key alone is a URL that reads and overwrites."""
        token = signer.sign(SignedGrant("a.png", "GET", time.time() + 300))
        with pytest.raises(SignatureInvalid):
            signer.verify(token, key="a.png", method="PUT")

    def test_a_token_cannot_be_moved_to_another_object(self, signer):
        token = signer.sign(SignedGrant("a.png", "GET", time.time() + 300))
        with pytest.raises(SignatureInvalid):
            signer.verify(token, key="b.png", method="GET")

    def test_a_token_from_another_bucket_is_refused(self, signer):
        """The namespace is mixed into the key material, so one secret does not
        make every bucket's tokens interchangeable."""
        other = Signer("a-secret-that-is-long-enough", "exports")
        token = other.sign(SignedGrant("a.png", "GET", time.time() + 300))

        with pytest.raises(SignatureInvalid):
            signer.verify(token, key="a.png", method="GET")

    def test_a_token_from_another_secret_is_refused(self, signer):
        other = Signer("a-completely-different-secret", "avatars")
        token = other.sign(SignedGrant("a.png", "GET", time.time() + 300))

        with pytest.raises(SignatureInvalid):
            signer.verify(token, key="a.png", method="GET")

    def test_garbage_is_refused_rather_than_parsed(self, signer):
        for rubbish in ("", ".", "x", "a.b", "not-a-token"):
            with pytest.raises(SignatureInvalid):
                signer.verify(rubbish, key="a.png", method="GET")

    def test_every_refusal_says_the_same_thing(self, signer):
        """Telling an unauthenticated caller which check failed tells them how
        the signing works."""
        messages = set()

        for token in (
            signer.sign(SignedGrant("a.png", "GET", time.time() - 1)),
            signer.sign(SignedGrant("b.png", "GET", time.time() + 300)),
            "rubbish.rubbish",
        ):
            try:
                signer.verify(token, key="a.png", method="GET")
            except SignatureInvalid as error:
                messages.add(str(error))

        assert len(messages) == 1

    def test_the_grant_carries_its_limits(self, signer):
        grant = SignedGrant("a.png", "PUT", time.time() + 300, "image/png", 1024)
        verified = signer.verify(signer.sign(grant), key="a.png", method="PUT")

        assert verified.content_type == "image/png"
        assert verified.max_bytes == 1024

    def test_a_short_secret_is_refused_at_construction(self):
        """A signer built with nothing would mint forgeable tokens silently."""
        with pytest.raises(ValueError, match="at least 16 bytes"):
            Signer("short", "avatars")


class TestForgedClaims:
    """A payload that survives the MAC check is genuine; one that does not
    should be refused rather than parsed. These cover the path where a token is
    well-formed base64 and its claims are the wrong shape."""

    def test_claims_of_the_wrong_type_are_refused(self):
        import base64
        import json

        signer = Signer("a-secret-that-is-long-enough", "avatars")
        payload = base64.urlsafe_b64encode(
            json.dumps({"v": "v1", "k": "a.png", "m": "GET", "e": {}, "c": "", "s": 0}).encode()
        ).decode().rstrip("=")

        # Signed correctly, so it passes the MAC and reaches the parsing.
        token = f"{payload}.{signer._mac(payload)}"

        with pytest.raises(SignatureInvalid):
            signer.verify(token, key="a.png", method="GET")

    def test_a_claim_set_that_is_not_an_object_is_refused(self):
        import base64
        import json

        signer = Signer("a-secret-that-is-long-enough", "avatars")
        payload = base64.urlsafe_b64encode(json.dumps([1, 2, 3]).encode()).decode().rstrip("=")
        token = f"{payload}.{signer._mac(payload)}"

        with pytest.raises(SignatureInvalid):
            signer.verify(token, key="a.png", method="GET")

    def test_an_old_version_is_refused(self):
        """So a token minted under one claim interpretation cannot be replayed
        against a newer one."""
        import base64
        import json

        signer = Signer("a-secret-that-is-long-enough", "avatars")
        payload = base64.urlsafe_b64encode(
            json.dumps({"v": "v0", "k": "a.png", "m": "GET", "e": 9e9}).encode()
        ).decode().rstrip("=")
        token = f"{payload}.{signer._mac(payload)}"

        with pytest.raises(SignatureInvalid):
            signer.verify(token, key="a.png", method="GET")
