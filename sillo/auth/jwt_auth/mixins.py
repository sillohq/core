from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sillo.auth.jwt_auth.models import JWTToken, TokenBlacklist
from sillo.auth.jwt_auth.tokens import TokenForUser


class JWTUserMixin:
    """Mixin that adds JWT token lifecycle management to a user model.

    Provides methods for issuing access/refresh token pairs, rotating
    refresh tokens with theft detection, revoking all tokens for a user,
    blacklisting individual tokens, and counting currently active tokens.
    This mixin expects the host class to expose an ``identity`` attribute
    that can be cast to ``int`` to obtain the user's primary key.
    """

    async def issue_token_pair(
        self,
        secret: str,
        access_expires: Optional[timedelta] = None,
        refresh_expires: Optional[timedelta] = None,
        algorithm: str = "HS256",
    ) -> dict:
        """Issue a new access and refresh token pair for this user.

        Generates a fresh token family, creates unique JTIs for both tokens,
        encodes them via :class:`TokenForUser`, and persists tracking rows
        in the :class:`JWTToken` table for later revocation and rotation.

        Args:
            secret: The symmetric secret key used to sign both tokens.
            access_expires: How long the access token should remain valid.
                Defaults to 15 minutes when ``None``.
            refresh_expires: How long the refresh token should remain valid.
                Defaults to 7 days when ``None``.
            algorithm: The signing algorithm for both tokens. Defaults to
                ``"HS256"``.

        Returns:
            A dictionary with keys ``access_token``, ``refresh_token``,
            ``token_type`` (always ``"bearer"``), and ``token_family``
            (a hex string linking the two tokens together).

        Raises:
            Exception: If token encoding or database persistence fails for
                any reason.
        """
        tokens = TokenForUser(self, secret=secret, algorithm=algorithm)
        family = secrets.token_hex(32)
        access_jti = secrets.token_hex(16)
        access = tokens.access_token(access_expires or timedelta(minutes=15))
        refresh_jti = secrets.token_hex(16)
        refresh = tokens.refresh_token(refresh_expires or timedelta(days=7))
        now = datetime.now(timezone.utc)
        await JWTToken.create(
            user_id=int(str(self.identity)),
            token_jti=access_jti,
            token_family=family,
            token_type="access",
            expires_at=now + (access_expires or timedelta(minutes=15)),
        )
        await JWTToken.create(
            user_id=int(str(self.identity)),
            token_jti=refresh_jti,
            token_family=family,
            token_type="refresh",
            expires_at=now + (refresh_expires or timedelta(days=7)),
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "token_family": family,
        }

    async def refresh_token_pair(
        self,
        refresh_token: str,
        secret: str,
        algorithm: str = "HS256",
    ) -> dict:
        """Rotate a refresh token and issue a new access/refresh token pair.

        Verifies the supplied refresh token without checking expiration,
        looks up its tracking row, and performs theft-detection checks:
        if the token's family has been revoked or the token has already
        been consumed, the entire family is revoked and an error is raised.
        On success the old refresh token is marked as consumed and a new
        pair is generated within the same token family.

        Args:
            refresh_token: The compact JWT refresh token string to rotate.
            secret: The symmetric secret key used to verify and sign tokens.
            algorithm: The signing algorithm for the new tokens. Defaults
                to ``"HS256"``.

        Returns:
            A dictionary with keys ``access_token``, ``refresh_token``,
            ``token_type`` (always ``"bearer"``), and ``token_family``
            (the existing family hex string carried over from the old token).

        Raises:
            ValueError: With message ``"Invalid refresh token"`` if the token
                cannot be decoded, ``"Unknown refresh token"`` if no tracking
                row exists, or messages about token theft if the family has
                been revoked or the token was already consumed.
        """
        tokens = TokenForUser(self, secret=secret, algorithm=algorithm)
        try:
            payload = tokens.verify_no_expire(refresh_token)
        except Exception:
            raise ValueError("Invalid refresh token")
        jti = payload.get("jti", refresh_token)
        existing = await JWTToken.filter(token_jti=jti).first()
        if existing is None or existing.token_type != "refresh":
            raise ValueError("Unknown refresh token")
        if existing.revoked:
            await JWTToken.revoke_family(existing.token_family)
            raise ValueError("Token family has been revoked — possible token theft")
        if existing.consumed_at is not None:
            await JWTToken.revoke_family(existing.token_family)
            raise ValueError("Refresh token already consumed — possible token theft")
        await existing.consume()
        family = existing.token_family
        access_expires = timedelta(minutes=15)
        refresh_expires = timedelta(days=7)
        access_jti = secrets.token_hex(16)
        access = tokens.access_token(access_expires)
        refresh_jti = secrets.token_hex(16)
        refresh = tokens.refresh_token(refresh_expires)
        now = datetime.now(timezone.utc)
        await JWTToken.create(
            user_id=int(str(self.identity)),
            token_jti=access_jti,
            token_family=family,
            token_type="access",
            expires_at=now + access_expires,
        )
        await JWTToken.create(
            user_id=int(str(self.identity)),
            token_jti=refresh_jti,
            token_family=family,
            token_type="refresh",
            expires_at=now + refresh_expires,
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "token_family": family,
        }

    async def revoke_all_tokens(self) -> int:
        """Revoke every JWT token currently issued to this user.

        Delegates to :meth:`JWTToken.revoke_all_for_user` to mark all
        non-revoked tokens for this user as revoked in the database. This
        effectively invalidates all outstanding access and refresh tokens.

        Returns:
            The number of tokens that were revoked by this operation.

        Raises:
            tortoise.exceptions.OperationalError: If the database update
                fails due to a connection or integrity issue.
        """
        return await JWTToken.revoke_all_for_user(int(str(self.identity)))

    async def blacklist_token(self, token: str, secret: str) -> bool:
        """Add a token's JTI to the blacklist table to prevent future use.

        Decodes the token without expiration checking to extract the ``jti``
        and ``exp`` claims, then inserts a row into :class:`TokenBlacklist`.
        If the token lacks an ``exp`` claim, a default expiration of 30 days
        from now is used for the blacklist entry.

        Args:
            token: The compact JWT string to blacklist.
            secret: The symmetric secret key used to decode the token and
                extract its claims.

        Returns:
            ``True`` if the token was successfully decoded and added to the
            blacklist, ``False`` if decoding failed.

        Raises:
            None. Decoding failures are caught internally and result in a
                ``False`` return value.
        """
        try:
            payload = TokenForUser(self, secret=secret).verify_no_expire(token)
        except Exception:
            return False
        jti = payload.get("jti", token)
        exp = payload.get("exp")
        if exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        await TokenBlacklist.get_or_create(
            token_jti=jti,
            defaults={"expires_at": expires_at},
        )
        return True

    async def active_token_count(self) -> int:
        """Count the number of non-revoked, non-expired tokens for this user.

        Queries the :class:`JWTToken` table for rows belonging to this user
        that have not been revoked and whose expiration timestamp is still
        in the future. This provides a snapshot of how many valid tokens
        are currently outstanding.

        Returns:
            An integer count of active tokens. Returns ``0`` if the user
            has no valid tokens.

        Raises:
            tortoise.exceptions.OperationalError: If the database query
                fails due to a connection issue.
        """
        return await JWTToken.filter(
            user_id=int(str(self.identity)),
            revoked=False,
            expires_at__gt=datetime.now(timezone.utc),
        ).count()
