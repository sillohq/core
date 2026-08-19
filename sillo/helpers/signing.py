import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Any


class BadSignature(Exception):
    """Raised when a signature cannot be verified."""


class SignatureExpired(BadSignature):
    """Raised when a signature is valid but the token is older than ``max_age``.

    A subclass of :class:`BadSignature` so that callers which only care about
    "this token is not usable" keep working unchanged, while callers that want
    to tell a forgery from an expiry can catch this one first.
    """


def _derive_key(secret_key: bytes, salt: bytes) -> bytes:
    """Mix *salt* into *secret_key* to get a key specific to one purpose.

    The salt used to be prepended to the signed data instead —
    ``hmac(key, salt + data)`` — which is not domain separation: it leaves
    ``(salt="ab", data="cd")`` and ``(salt="a", data="bcd")`` signing the exact
    same bytes, so a token minted for one purpose can verify under another.
    Deriving a distinct key per salt makes the separation a property of the
    key rather than of how two strings happen to concatenate.
    """
    return hmac.new(secret_key, salt, hashlib.sha256).digest()


class URLSafeSerializer:
    """Sign JSON payloads into compact, URL-safe, tamper-evident tokens.

    The token is ``<payload>.<signature>``, both base64url without padding.
    The payload is **signed, not encrypted** — anyone holding a token can
    base64-decode it and read the data. Never put anything in one that the
    holder is not allowed to see.
    """

    def __init__(self, secret_key: str, salt: str = "") -> None:
        """Init"""
        self.secret_key = secret_key.encode("utf-8")
        self.salt = salt.encode("utf-8")
        self._key = _derive_key(self.secret_key, self.salt)

    def _sign(self, data: bytes) -> bytes:
        return hmac.new(self._key, data, hashlib.sha256).digest()

    def _signature_for(self, payload_b64: bytes) -> str:
        """Return the base64url signature over *payload_b64*, unpadded."""
        return (
            base64.urlsafe_b64encode(self._sign(payload_b64))
            .rstrip(b"=")
            .decode("ascii")
        )

    def _verify(self, payload_b64: bytes, signature_b64: str) -> bool:
        """Compare signatures in their encoded form.

        Comparing the base64 text rather than the decoded digests means
        nothing from an untrusted token is decoded before it has been
        authenticated — the decoders are lenient (``b64decode`` silently drops
        characters outside the alphabet), and lenient parsing of attacker-
        supplied bytes is worth keeping on the far side of the check.
        """
        return hmac.compare_digest(self._signature_for(payload_b64), signature_b64)

    def _split(self, token: str) -> tuple[bytes, str]:
        """Split *token* into its payload and signature, or raise.

        Rejects anything outside ASCII first. A token arrives from a cookie,
        so its bytes are whoever sent it's to choose, and neither of the two
        things that happen next tolerates the choice: ``str.encode("ascii")``
        raises ``UnicodeEncodeError`` and ``hmac.compare_digest`` raises
        ``TypeError: comparing strings with non-ASCII characters``. Both came
        out of the middleware uncaught, so a one-byte cookie was a 500.
        """
        if not token.isascii():
            raise BadSignature("Invalid token format")

        payload_b64, separator, signature_b64 = token.rpartition(".")
        if not separator:
            raise BadSignature("Invalid token format")
        return payload_b64.encode("ascii"), signature_b64

    def dumps(self, obj: Any) -> str:
        """Sign *obj* and return the token."""
        payload = base64.urlsafe_b64encode(
            json.dumps(obj, separators=(",", ":")).encode("utf-8")
        ).rstrip(b"=")
        return f"{payload.decode('ascii')}.{self._signature_for(payload)}"

    def loads(self, token: str) -> Any:
        """Verify *token* and return what was signed.

        Raises:
            BadSignature: If the token is malformed or the signature does not
                verify. The payload is only decoded once the signature has
                been checked.
        """
        payload_b64, signature_b64 = self._split(token)

        if not self._verify(payload_b64, signature_b64):
            raise BadSignature("Signature invalid")

        return json.loads(_b64_decode(payload_b64.decode("ascii")))


class URLSafeTimedSerializer(URLSafeSerializer):
    """A :class:`URLSafeSerializer` whose tokens carry the time they were made.

    The timestamp is inside the signed payload, so it cannot be moved without
    breaking the signature — but it only means anything if :meth:`loads` is
    given a ``max_age`` to compare it against.
    """

    #: Tolerance, in seconds, for a token stamped slightly in the future.
    #: Signing and verifying can happen on different machines, and a clock a
    #: few seconds ahead should not lock a user out.
    clock_skew: int = 60

    def dumps(self, obj: Any) -> str:
        """Sign *obj* together with the current time."""
        data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time())).encode("ascii")
        payload = base64.urlsafe_b64encode(timestamp + b"." + data).rstrip(b"=")
        return f"{payload.decode('ascii')}.{self._signature_for(payload)}"

    def loads(self, token: str, max_age: int | None = None) -> Any:
        """Verify *token*, check its age, and return what was signed.

        Args:
            max_age: How many seconds old the token may be. ``None`` means the
                age is not checked at all — which is almost never what a
                caller wants for anything reaching it from a browser, since a
                token that never expires is one a thief keeps forever.

        Raises:
            SignatureExpired: If the token is older than *max_age*, or is
                stamped far enough in the future that it cannot be genuine.
            BadSignature: If the token is malformed or does not verify.
        """
        payload_b64, signature_b64 = self._split(token)

        if not self._verify(payload_b64, signature_b64):
            raise BadSignature("Signature invalid")

        payload_bytes = _b64_decode(payload_b64.decode("ascii"))
        timestamp_b64, separator, data = payload_bytes.partition(b".")

        if not separator:
            # A validly signed payload with no timestamp: an untimed
            # serializer's token reaching a timed one. Signed by us, so not an
            # attack, but it is not a timed token either and `int()` on the
            # JSON body would raise ValueError straight out of the middleware.
            raise BadSignature("Token carries no timestamp")

        try:
            timestamp = int(timestamp_b64)
        except ValueError:
            raise BadSignature("Token timestamp is not a number") from None

        age = time.time() - timestamp

        if max_age is not None and age > max_age:
            raise SignatureExpired("Token expired")

        if age < -self.clock_skew:
            raise SignatureExpired("Token is stamped in the future")

        return json.loads(data)


def _b64_decode(data: str) -> bytes:
    """Decode unpadded base64url, restoring the padding first.

    Raises:
        BadSignature: If *data* is not decodable. Callers reach this only
            after a signature check, so a failure here means a payload this
            process signed can no longer be read — still not something to
            raise a raw ``binascii.Error`` out of a request for.
    """
    padding = -len(data) % 4
    try:
        return base64.urlsafe_b64decode(data + "=" * padding)
    except (binascii.Error, ValueError):
        raise BadSignature("Invalid token format") from None
