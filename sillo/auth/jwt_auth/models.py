from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from tortoise import fields

from sillo.record import Model, TimestampsMixin


class JWTToken(Model, TimestampsMixin):
    """Issued JWT token — enables refresh chains, family rotation, and revocation.

    Each access + refresh pair shares a ``token_family``. On refresh, the old
    token is marked consumed and a new pair is created. Reuse detection:
    if a consumed refresh token is presented, the entire family is revoked.

    This model serves as the single source of truth for all issued JWT tokens
    in the system. It tracks the complete lifecycle of each token from creation
    through consumption, expiration, and revocation. The token family mechanism
    enables secure rotation by linking access and refresh token pairs together,
    allowing the system to detect token reuse attacks and respond by revoking
    all tokens in the compromised family.

    Attributes:
        id: The primary key identifier for the token record.
        user_id: The ID of the user this token was issued to, indexed for lookup.
        token_jti: A unique JWT ID claim value, used for individual token lookup.
        token_family: Groups related access/refresh token pairs for rotation.
        token_type: Either 'access' or 'refresh' indicating the token purpose.
        expires_at: The UTC datetime when this token is no longer valid.
        consumed_at: The UTC datetime when this token was consumed during refresh.
        revoked: Boolean flag indicating whether this token has been revoked.
    """

    id = fields.IntField(pk=True)
    user_id = fields.IntField(index=True)
    token_jti = fields.CharField(max_length=255, unique=True, index=True)
    token_family = fields.CharField(max_length=64, index=True)
    token_type = fields.CharField(max_length=16, default="access")
    expires_at = fields.DatetimeField()
    consumed_at = fields.DatetimeField(null=True, default=None)
    revoked = fields.BooleanField(default=False)

    class Meta:
        """Tortoise ORM metadata configuration for the JWTToken model.

        Defines the database table name and any model-level ORM settings.
        This inner class is consumed by the Tortoise ORM framework to
        configure table mapping and query behavior for the JWTToken model.

        Attributes:
            table: The name of the database table for storing JWT token records.
        """

        table = "jwt_tokens"

    @property
    def is_expired(self) -> bool:
        """Check whether this token has passed its expiration time.

        Compares the current UTC time against the token's ``expires_at``
        field to determine if the token is still temporally valid. This
        check does not consider revocation or consumption status; use
        ``is_active`` for a comprehensive validity check.

        Returns:
            bool: True if the current UTC time is past the token's
                expiration time, False otherwise.
        """
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_active(self) -> bool:
        """Check whether this token is currently valid for use.

        A token is considered active when it has not been revoked and has
        not yet expired. This property combines revocation status with
        temporal expiration to provide a single authoritative check for
        token validity before granting access to protected resources.

        Returns:
            bool: True if the token is neither revoked nor expired,
                False if either condition indicates invalidity.
        """
        return not self.revoked and not self.is_expired

    async def consume(self) -> None:
        """Mark this token as consumed during a refresh token rotation.

        Sets the ``consumed_at`` timestamp to the current UTC time and
        persists the change to the database. Consuming a token indicates
        that it has been exchanged for a new token pair as part of the
        refresh flow. If a consumed token is presented again, the reuse
        detection logic should trigger a full family revocation.

        Returns:
            None: This method does not return a value.
        """
        self.consumed_at = datetime.now(timezone.utc)
        await self.save(update_fields=["consumed_at"])

    async def revoke(self) -> None:
        """Revoke this token, permanently invalidating it for future use.

        Sets the ``revoked`` flag to True and persists the change to the
        database. Once revoked, the token will fail all validity checks
        regardless of its expiration time or consumption status. This is
        typically called during logout or when suspicious activity is
        detected on the token or its associated family.

        Returns:
            None: This method does not return a value.
        """
        self.revoked = True  # ty: ignore[invalid-assignment]
        await self.save(update_fields=["revoked"])

    @classmethod
    async def revoke_family(cls, token_family: str) -> int:
        """Revoke all tokens belonging to a specific token family.

        Marks every token in the given family as revoked and persists the
        changes to the database. This is the response to a detected token
        reuse attack: when a previously consumed refresh token is presented
        again, the entire family is considered compromised and all tokens
        within it are invalidated to prevent further unauthorized access.

        Args:
            token_family: The unique family identifier whose tokens should
                all be revoked. All tokens sharing this family value will
                have their ``revoked`` flag set to True.

        Returns:
            int: The count of tokens that were newly revoked (i.e., tokens
                that were not already revoked before this call).
        """
        count = await cls.filter(token_family=token_family, revoked=False).count()
        await cls.filter(token_family=token_family).update(revoked=True)
        return count

    @classmethod
    async def revoke_all_for_user(cls, user_id: int) -> int:
        """Revoke all tokens issued to a specific user.

        Marks every token belonging to the given user as revoked and persists
        the changes to the database. This is typically invoked during a
        full logout, account suspension, or security incident where all
        active sessions for a user must be terminated immediately.

        Args:
            user_id: The unique identifier of the user whose tokens should
                all be revoked. Every token record with this ``user_id``
                will have its ``revoked`` flag set to True.

        Returns:
            int: The count of tokens that were newly revoked (i.e., tokens
                that were not already revoked before this call).
        """
        count = await cls.filter(user_id=user_id, revoked=False).count()
        await cls.filter(user_id=user_id).update(revoked=True)
        return count

    @classmethod
    async def cleanup_expired(cls) -> int:
        """Remove all expired token records from the database.

        Queries for all tokens whose ``expires_at`` timestamp is in the past
        and deletes them from the database. This is a maintenance operation
        intended to be run periodically to prevent unbounded growth of the
        tokens table. Expired tokens that have already been consumed or
        revoked are also removed since they serve no further purpose.

        Returns:
            int: The number of expired token records that were deleted
                from the database during this cleanup operation.
        """
        now = datetime.now(timezone.utc)
        expired = await cls.filter(expires_at__lt=now).all()
        count = len(expired)
        for token in expired:
            await token.delete()
        return count


class TokenBlacklist(Model, TimestampsMixin):
    """Token blacklist — for immediate invalidation of specific tokens.

    Provides a mechanism to blacklist individual JWT tokens by their unique
    JTI claim before their natural expiration. This is useful for scenarios
    where a token must be invalidated immediately, such as when a security
    breach is detected or when a user reports a stolen token. Entries in
    this table are checked during token verification to reject blacklisted
    tokens even if they would otherwise pass signature and expiration checks.

    Attributes:
        id: The primary key identifier for the blacklist entry.
        token_jti: The unique JWT ID of the blacklisted token.
        blacklisted_at: The UTC datetime when this token was blacklisted.
        expires_at: The original expiration time of the blacklisted token,
            used to determine when the blacklist entry can be pruned.
    """

    id = fields.IntField(pk=True)
    token_jti = fields.CharField(max_length=512, unique=True, index=True)
    blacklisted_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField()

    class Meta:
        """Tortoise ORM metadata configuration for the TokenBlacklist model.

        Defines the database table name and any model-level ORM settings.
        This inner class is consumed by the Tortoise ORM framework to
        configure table mapping and query behavior for the TokenBlacklist
        model, which stores revoked JWT token identifiers.

        Attributes:
            table: The name of the database table for storing blacklist entries.
        """

        table = "token_blacklist"

    @classmethod
    async def prune_expired(cls) -> int:
        """Remove blacklist entries whose tokens have naturally expired.

        Queries for all blacklist entries whose ``expires_at`` timestamp is
        in the past and deletes them from the database. Since a token cannot
        be used after its expiration time, blacklist entries for expired
        tokens are redundant and can be safely removed. This is a maintenance
        operation intended to be run periodically to keep the blacklist table
        from growing indefinitely with entries that no longer serve a purpose.

        Returns:
            int: The number of expired blacklist entries that were deleted
                from the database during this pruning operation.
        """
        now = datetime.now(timezone.utc)
        expired = await cls.filter(expires_at__lt=now).all()
        count = len(expired)
        for entry in expired:
            await entry.delete()
        return count
