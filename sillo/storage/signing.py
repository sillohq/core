"""
sillo.storage.signing — a URL that grants one narrow permission for a while.

S3 can sign; local disk cannot.  Rather than admit a hole in the contract — and
put a branch in every project that might one day switch backend — the framework
signs for local itself, and :mod:`sillo.storage.routes` mounts one route that
verifies.

What is signed is the whole permission, not just the key:

    key · method · expiry · content type · maximum size

All five, because each one left out is a permission accidentally granted.  A
signature over the key alone is a URL that reads *and* overwrites.  One without
the content type lets an uploader who was handed a slot for ``image/png`` store
HTML in it.  One without a size limit lets them store a hundred gigabytes.

The token is opaque and carries its own claims, so verification needs no lookup
and no shared state — the same reason sillo-oauth derives its PKCE verifier
instead of storing it.

Comparison is constant-time.  Not because a timing attack on a development
file server is likely, but because ``==`` on a secret is the kind of thing that
gets copied into somewhere it matters.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from .errors import SignatureInvalid

__all__ = ["SignedGrant", "Signer"]

#: Bumped if the claim set ever changes, so an old token cannot be replayed
#: against a new interpretation of its fields.
VERSION = "v1"


class SignedGrant:
    """What a signature permits.

    Attributes:
        key: The one object.
        method: The one HTTP method.
        expires: Unix timestamp after which it is refused.
        content_type: The one content type a write may carry, or empty for any.
        max_bytes: The largest body a write may carry, or zero for unlimited.
    """

    __slots__ = ("content_type", "expires", "key", "max_bytes", "method")

    def __init__(
        self,
        key: str,
        method: str,
        expires: float,
        content_type: str = "",
        max_bytes: int = 0,
    ) -> None:
        """Build a grant.

        Args:
            key: The object's key.
            method: The permitted method.
            expires: When it stops working.
            content_type: The permitted content type.
            max_bytes: The permitted body size.
        """
        self.key = key
        self.method = method.upper()
        self.expires = expires
        self.content_type = content_type
        self.max_bytes = max_bytes

    @property
    def expired(self) -> bool:
        """Whether the grant has run out.

        Returns:
            True when the expiry has passed.
        """
        return time.time() > self.expires

    def claims(self) -> dict[str, object]:
        """The grant as the data that gets signed.

        Returns:
            The claims, in a fixed key order so the same grant always produces
            the same bytes.
        """
        return {
            "v": VERSION,
            "k": self.key,
            "m": self.method,
            "e": int(self.expires),
            "c": self.content_type,
            "s": self.max_bytes,
        }

    def __repr__(self) -> str:
        """A short description for debugging.

        Returns:
            What it permits, without the signature.
        """
        return (
            f"SignedGrant({self.method} {self.key!r}, "
            f"expires_in={int(self.expires - time.time())}s)"
        )


class Signer:
    """Mints and checks signed grants.

    Attributes:
        namespace: Mixed into the key material, so a token minted for one
            bucket cannot be presented to another even under the same secret.
    """

    __slots__ = ("_key", "namespace")

    def __init__(self, secret: str | bytes, namespace: str = "") -> None:
        """Build a signer.

        Args:
            secret: The application secret.
            namespace: Usually the bucket's name.

        Raises:
            ValueError: If the secret is empty or obviously too short to be
                one. Failing here is the point: a signer built with ``""``
                would mint tokens anybody could forge, and would do it
                silently.
        """
        material = secret.encode() if isinstance(secret, str) else secret

        if len(material) < 16:
            raise ValueError(
                "a signing secret must be at least 16 bytes; this one is "
                f"{len(material)}"
            )

        self.namespace = namespace
        # Derived rather than used directly, so the application secret is not
        # the key for anything else that might also use HMAC-SHA256.
        self._key = hmac.new(
            material, f"sillo-storage/{VERSION}/{namespace}".encode(), hashlib.sha256
        ).digest()

    def sign(self, grant: SignedGrant) -> str:
        """Mint a token for a grant.

        Args:
            grant: What to permit.

        Returns:
            An opaque token, safe in a URL.
        """
        payload = _encode(grant.claims())
        return f"{payload}.{self._mac(payload)}"

    def verify(self, token: str, *, key: str, method: str) -> SignedGrant:
        """Check a token, and say what it permits.

        Args:
            token: The token from the URL.
            key: The object actually being reached for.
            method: The method actually being used.

        Returns:
            The grant, when it is valid for this request.

        Raises:
            SignatureInvalid: If the token is malformed, forged, expired, or
                was minted for a different object or method. One error for all
                of them: telling an unauthenticated caller *which* applies
                tells them how the signing works.
        """
        payload, _, mac = token.partition(".")

        if not payload or not mac:
            raise SignatureInvalid("malformed token")

        # Before anything is decoded. A forged payload should never be parsed,
        # let alone acted on.
        if not hmac.compare_digest(mac, self._mac(payload)):
            raise SignatureInvalid("bad signature")

        try:
            claims = _decode(payload)
        except Exception as error:
            raise SignatureInvalid("malformed token") from error

        if claims.get("v") != VERSION:
            raise SignatureInvalid("bad signature")

        # str() around the numbers as well: the claims came off the wire, and
        # `float(some_dict)` is a TypeError rather than a refusal — a forged
        # payload should be rejected, not crash the verifier.
        try:
            grant = SignedGrant(
                key=str(claims.get("k", "")),
                method=str(claims.get("m", "")),
                expires=float(str(claims.get("e", 0))),
                content_type=str(claims.get("c", "")),
                max_bytes=int(str(claims.get("s", 0))),
            )
        except (TypeError, ValueError) as error:
            raise SignatureInvalid("malformed token") from error

        if grant.expired:
            raise SignatureInvalid("bad signature")

        # The token is genuine; it may still be for something else. Binding the
        # grant to the request is what stops a read token being replayed as a
        # write, or against another object.
        if grant.key != key or grant.method != method.upper():
            raise SignatureInvalid("bad signature")

        return grant

    def _mac(self, payload: str) -> str:
        """The signature over an encoded payload.

        Args:
            payload: The encoded claims.

        Returns:
            The MAC, base64url without padding.
        """
        digest = hmac.new(self._key, payload.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    def __repr__(self) -> str:
        """A description that does not include the key.

        Returns:
            The namespace only.
        """
        return f"Signer(namespace={self.namespace!r})"


def _encode(claims: dict[str, object]) -> str:
    """Encode claims for a URL.

    Args:
        claims: The claim set.

    Returns:
        base64url without padding.
    """
    raw = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(payload: str) -> dict[str, object]:
    """Decode claims from a URL.

    Args:
        payload: The encoded claims.

    Returns:
        The claim set.
    """
    padding = "=" * (-len(payload) % 4)
    raw = base64.urlsafe_b64decode(payload + padding)
    decoded = json.loads(raw)

    if not isinstance(decoded, dict):
        raise ValueError("claims are not an object")

    return decoded
