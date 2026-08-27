from __future__ import annotations

import datetime
import json
from typing import Any

try:
    import jwt as pyjwt
    from jwt.exceptions import (
        DecodeError,
        ExpiredSignatureError,
        InvalidTokenError,
    )

    _jwt_available = True
except ImportError:  # pragma: no cover - exercised only without PyJWT installed
    _jwt_available = False
    pyjwt = None  # type: ignore
    ExpiredSignatureError = Exception  # ty: ignore[invalid-assignment]
    InvalidTokenError = Exception  # ty: ignore[invalid-assignment]
    DecodeError = Exception  # ty: ignore[invalid-assignment]


class TokenError(Exception):
    """Base exception for all JWT token-related errors.

    Serves as the parent class for more specific token errors such as
    ``ExpiredTokenError`` and ``InvalidTokenError_``. Catching this
    exception allows callers to handle any token-related failure in
    a single except block while still distinguishing token issues
    from other exception types in the application.
    """


class ExpiredTokenError(TokenError):
    """Exception raised when a JWT token has passed its expiration time.

    Indicates that the token was structurally valid but its ``exp`` claim
    shows it is no longer within the acceptable time window. Callers should
    treat this as a signal to request a fresh token, typically by using
    a refresh token or re-authenticating the user.
    """


class InvalidTokenError_(TokenError):
    """Exception raised when a JWT token is malformed or fails verification.

    Indicates that the token could not be decoded or its signature does
    not match the expected secret. This covers cases such as tampered
    payloads, incorrect signing algorithms, or corrupted token strings.
    """


def _ensure_jwt():
    """Verify that the PyJWT library is available in the current environment.

    Checks whether the optional ``PyJWT`` dependency was successfully imported
    at module load time. If the library is missing, raises an ``ImportError``
    with installation instructions so that callers receive a clear actionable
    message instead of a cryptic ``NameError`` at runtime.

    Raises:
        ImportError: If PyJWT is not installed, with a message containing
            the pip install command needed to resolve the issue.
    """
    if not _jwt_available:
        raise ImportError(
            "PyJWT is required for JWT helpers. Install with: pip install pyjwt"
        )


def encode(
    payload: dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    headers: dict[str, Any] | None = None,
) -> str:
    """Encode a dictionary payload into a signed JWT token string.

    Creates a JSON Web Token by encoding the provided payload, signing it
    with the given secret using the specified algorithm, and returning the
    compact serialized token string. Optional extra headers can be included
    in the token header for use cases such as key identification.

    Args:
        payload: A dictionary containing the claims to encode in the token.
        secret: The secret key used to sign the token.
        algorithm: The signing algorithm to use. Defaults to ``HS256``.
        headers: An optional dictionary of additional header fields to
            include in the JWT header section.

    Returns:
        A compact JWT token string consisting of three base64url-encoded
        sections separated by dots.

    Raises:
        ImportError: If PyJWT is not installed.
    """
    _ensure_jwt()
    return pyjwt.encode(payload, secret, algorithm=algorithm, headers=headers)


def decode(
    token: str,
    secret: str,
    algorithms: list[str] | None = None,
    options: dict[str, Any] | None = None,
    audience: str | None = None,
    issuer: str | None = None,
    leeway: int = 0,
) -> dict[str, Any]:
    """Decode and verify a JWT token, returning its payload as a dictionary.

    Validates the token signature against the provided secret, checks
    standard claims such as expiration, audience, and issuer, and returns
    the decoded payload. Expired tokens raise ``ExpiredTokenError`` and
    structurally invalid tokens raise ``InvalidTokenError_``.

    Args:
        token: The compact JWT token string to decode and verify.
        secret: The secret key used to verify the token signature.
        algorithms: An optional list of acceptable signing algorithms.
            Defaults to ``["HS256"]``.
        options: An optional dictionary of PyJWT decode options to
            customize verification behavior.
        audience: An optional expected audience claim value to validate.
        issuer: An optional expected issuer claim value to validate.
        leeway: Number of seconds of leeway allowed for time-based
            claim validation. Defaults to ``0``.

    Returns:
        The decoded payload dictionary containing all claims from the token.

    Raises:
        ExpiredTokenError: If the token has expired.
        InvalidTokenError_: If the token is malformed or signature is invalid.
        ImportError: If PyJWT is not installed.
    """
    _ensure_jwt()
    try:
        return pyjwt.decode(
            token,
            secret,
            algorithms=algorithms or ["HS256"],
            options=options,  # ty: ignore[invalid-argument-type]
            audience=audience,
            issuer=issuer,
            leeway=leeway,
        )
    except ExpiredSignatureError:
        raise ExpiredTokenError("Token has expired")
    except (InvalidTokenError, DecodeError) as e:
        raise InvalidTokenError_(str(e))


def sign(
    payload: dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    headers: dict[str, Any] | None = None,
) -> bytes:
    """Sign a payload dictionary and return the JWT token as raw bytes.

    Similar to ``encode`` but returns the token as a UTF-8 encoded byte
    string rather than a regular string. This is useful when the token
    needs to be transmitted over binary protocols or stored in byte-oriented
    data structures.

    Args:
        payload: A dictionary containing the claims to encode in the token.
        secret: The secret key used to sign the token.
        algorithm: The signing algorithm to use. Defaults to ``HS256``.
        headers: An optional dictionary of additional header fields to
            include in the JWT header section.

    Returns:
        The JWT token encoded as a UTF-8 byte string.

    Raises:
        ImportError: If PyJWT is not installed.
    """
    _ensure_jwt()
    encoded = pyjwt.encode(payload, secret, algorithm=algorithm, headers=headers)
    return encoded.encode("utf-8") if isinstance(encoded, str) else encoded


def verify(
    token: str,
    secret: str,
    algorithms: list[str] | None = None,
) -> bool:
    """Verify a JWT token's signature and return a boolean validity result.

    Attempts to decode the token using the provided secret and algorithms.
    Returns ``True`` if the token is valid and ``False`` for any failure
    including expiration, invalid signature, or malformed structure. This
    provides a simple boolean interface for callers that do not need
    detailed error information.

    Args:
        token: The compact JWT token string to verify.
        secret: The secret key used to verify the token signature.
        algorithms: An optional list of acceptable signing algorithms.
            Defaults to ``["HS256"]``.

    Returns:
        ``True`` if the token is valid, ``False`` otherwise.

    Raises:
        ImportError: If PyJWT is not installed.
    """
    _ensure_jwt()
    try:
        pyjwt.decode(token, secret, algorithms=algorithms or ["HS256"])
        return True
    except (InvalidTokenError, ExpiredSignatureError, DecodeError):
        return False


def get_unverified_header(token: str) -> dict[str, Any]:
    """Extract the header section from a JWT token without verifying its signature.

    Decodes only the header portion of the token to inspect metadata such as
    the signing algorithm (``alg``) and key ID (``kid``). No signature
    verification is performed, so this should only be used for informational
    purposes and never as a security check.

    Args:
        token: The compact JWT token string whose header should be extracted.

    Returns:
        A dictionary containing the decoded header claims.

    Raises:
        ImportError: If PyJWT is not installed.
    """
    _ensure_jwt()
    return pyjwt.get_unverified_header(token)


def get_unverified_claims(token: str) -> dict[str, Any] | None:
    """Extract the payload claims from a JWT token without verifying its signature.

    Decodes the middle section of the token to inspect its claims without
    performing any signature verification. This is useful for reading
    non-sensitive metadata such as the subject or custom claims before
    performing full verification. Returns ``None`` if the token cannot
    be parsed.

    Args:
        token: The compact JWT token string whose payload should be extracted.

    Returns:
        A dictionary containing the decoded payload claims, or ``None``
        if the token structure is invalid or cannot be decoded.

    Raises:
        ImportError: If PyJWT is not installed.
    """
    _ensure_jwt()
    try:
        return json.loads(
            pyjwt.utils.base64url_decode(token.split(".")[1].encode()).decode()  # ty: ignore[possibly-missing-submodule]
        )
    except Exception:
        return None


def create_access_token(
    data: dict[str, Any],
    secret: str,
    expires_delta: datetime.timedelta | None = None,
    algorithm: str = "HS256",
    issuer: str | None = None,
) -> str:
    """Create a signed JWT access token with automatic expiration and issued-at claims.

    Builds an access token by copying the provided data, adding ``exp`` and
    ``iat`` timestamp claims, and optionally setting an ``iss`` issuer claim.
    If no expiration delta is provided, the token defaults to a 15-minute
    lifetime. The token is then signed with the given secret and algorithm.

    Args:
        data: A dictionary of custom claims to include in the token payload.
        secret: The secret key used to sign the token.
        expires_delta: An optional timedelta specifying the token's lifetime.
            Defaults to 15 minutes if not provided.
        algorithm: The signing algorithm to use. Defaults to ``HS256``.
        issuer: An optional issuer identifier to set in the ``iss`` claim.

    Returns:
        A compact JWT access token string with expiration and issued-at claims.

    Raises:
        ImportError: If PyJWT is not installed.
    """
    _ensure_jwt()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=15
        )
    to_encode.update(
        {"exp": expire, "iat": datetime.datetime.now(datetime.timezone.utc)}
    )
    if issuer:
        to_encode["iss"] = issuer
    return pyjwt.encode(to_encode, secret, algorithm=algorithm)


def create_refresh_token(
    data: dict[str, Any],
    secret: str,
    expires_delta: datetime.timedelta | None = None,
    algorithm: str = "HS256",
) -> str:
    """Create a signed JWT refresh token with automatic expiration and issued-at claims.

    Builds a refresh token by copying the provided data, adding ``exp`` and
    ``iat`` timestamp claims, and signing with the given secret. Refresh tokens
    are designed for longer lifetimes than access tokens. If no expiration
    delta is provided, the token defaults to a 7-day lifetime.

    Args:
        data: A dictionary of custom claims to include in the token payload.
        secret: The secret key used to sign the token.
        expires_delta: An optional timedelta specifying the token's lifetime.
            Defaults to 7 days if not provided.
        algorithm: The signing algorithm to use. Defaults to ``HS256``.

    Returns:
        A compact JWT refresh token string with expiration and issued-at claims.

    Raises:
        ImportError: If PyJWT is not installed.
    """
    _ensure_jwt()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=7
        )
    to_encode.update(
        {"exp": expire, "iat": datetime.datetime.now(datetime.timezone.utc)}
    )
    return pyjwt.encode(to_encode, secret, algorithm=algorithm)


def decode_without_verification(token: str) -> dict[str, Any]:
    """Decode a JWT token's payload without performing any signature verification.

    Extracts and returns the claims from the token payload while explicitly
    skipping signature validation. This is intended for debugging, logging,
    or pre-processing scenarios where the token content must be inspected
    before full verification. Callers must not rely on this function for
    any security-sensitive decisions.

    Args:
        token: The compact JWT token string to decode without verification.

    Returns:
        A dictionary containing the decoded payload claims.

    Raises:
        InvalidTokenError_: If the token cannot be decoded at all.
        ImportError: If PyJWT is not installed.
    """
    _ensure_jwt()
    try:
        return pyjwt.decode(token, options={"verify_signature": False})
    except Exception:
        raise InvalidTokenError_("Cannot decode token")


def validate_claims(
    payload: dict[str, Any],
    audience: str | None = None,
    issuer: str | None = None,
    leeway: int = 0,
) -> bool:
    """Validate standard JWT claims in a decoded payload dictionary.

    Checks the ``exp``, ``nbf``, ``aud``, and ``iss`` claims against the
    current time and the expected values. Supports an optional leeway in
    seconds for time-based comparisons to account for clock skew between
    systems. Returns ``False`` if any claim fails validation.

    Args:
        payload: A dictionary of decoded JWT claims to validate.
        audience: An optional expected audience value to match against
            the ``aud`` claim.
        issuer: An optional expected issuer value to match against
            the ``iss`` claim.
        leeway: Number of seconds of tolerance for time-based claim
            comparisons. Defaults to ``0``.

    Returns:
        ``True`` if all present claims pass validation, ``False`` if
        any claim is invalid or expired.
    """
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()

    if "exp" in payload:
        exp = payload["exp"]
        if isinstance(exp, datetime.datetime):
            exp = exp.timestamp()
        if now > exp + leeway:
            return False

    if "nbf" in payload:
        nbf = payload["nbf"]
        if isinstance(nbf, datetime.datetime):
            nbf = nbf.timestamp()
        if now < nbf - leeway:
            return False

    if audience and payload.get("aud") != audience:
        return False

    return not (issuer and payload.get("iss") != issuer)
