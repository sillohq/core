from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from tortoise import fields

from sillo.record import Model, TimestampsMixin


def generate_api_key(prefix: str = "sillo") -> tuple[str, str, str]:
    """Generate a new API key with a secure random component and its SHA-256 hash.

    Creates a cryptographically secure random token using ``secrets.token_urlsafe``
    and prepends the given prefix to form the full key. The raw token (without
    prefix) and the SHA-256 hex digest of the full key are also returned so that
    callers can store the hash for later verification without persisting the
    plaintext key.

    Args:
        prefix: A short string prepended to the random token to identify the
            key owner or system. Defaults to ``"sillo"``.

    Returns:
        A three-element tuple containing:
            - ``full_key``: The complete key string in the form ``"{prefix}_{raw}"``.
            - ``raw``: The raw random token without the prefix.
            - ``key_hash``: The SHA-256 hex digest of ``full_key``.

    Raises:
        TypeError: If ``prefix`` is not a string.
    """
    raw = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, raw, key_hash


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Verify a raw API key against a previously stored SHA-256 hash.

    Computes the SHA-256 hex digest of the provided raw key and performs a
    constant-time comparison against the stored hash to prevent timing attacks.
    This function should be used whenever an incoming request needs to be
    authenticated via its API key.

    Args:
        raw_key: The plaintext API key extracted from the request credentials.
        stored_hash: The SHA-256 hex digest that was stored when the key was
            originally created.

    Returns:
        ``True`` if the computed hash matches the stored hash, ``False``
        otherwise.

    Raises:
        TypeError: If either argument is not a string.
    """
    computed = hashlib.sha256(raw_key.encode()).hexdigest()
    return secrets.compare_digest(computed, stored_hash)


def hash_api_key(raw_key: str) -> str:
    """Compute the SHA-256 hex digest of a raw API key string.

    Produces a deterministic hash suitable for persistent storage and later
    lookup. The caller is responsible for ensuring the raw key is the full
    key string (including any prefix) before hashing.

    Args:
        raw_key: The plaintext API key to hash.

    Returns:
        A 64-character lowercase hexadecimal SHA-256 digest string.

    Raises:
        TypeError: If ``raw_key`` is not a string.
    """
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKey(Model, TimestampsMixin):
    """Database model representing a single API key record.

    Stores the hashed form of an API key along with metadata such as the
    owning user, assigned scopes, expiration timestamp, and last-used
    timestamp. Plaintext keys are never persisted; only SHA-256 hashes are
    stored for secure verification.

    Attributes:
        id: Auto-incrementing primary key.
        name: A human-readable label for the key.
        key_hash: Unique SHA-256 hex digest of the full API key string.
        last_used_at: Timestamp of the most recent successful authentication,
            or ``None`` if the key has never been used.
        expires_at: Optional expiration timestamp; ``None`` means the key
            never expires.
        is_active: Boolean flag indicating whether the key is currently valid.
        scopes: Optional JSON list of permission scope strings.
        user_id: Foreign key referencing the owning user.
    """

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    key_hash = fields.CharField(max_length=255, unique=True, index=True)
    last_used_at = fields.DatetimeField(null=True, default=None)
    expires_at = fields.DatetimeField(null=True, default=None)
    is_active = fields.BooleanField(default=True)
    scopes = fields.JSONField(null=True, default=None)
    user_id = fields.IntField(index=True)

    class Meta:
        """Tortoise ORM meta configuration for the ApiKey model.

        Specifies the physical database table name and any ORM-level
        options that control how Tortoise interacts with this model at
        runtime.

        Attributes:
            table: The name of the database table backing this model.
        """

        table = "api_keys"

    @property
    def is_expired(self) -> bool:
        """Check whether this API key has passed its expiration timestamp.

        Compares the current UTC time against the ``expires_at`` field. If
        ``expires_at`` is ``None`` the key is considered to have no
        expiration and this property returns ``False``.

        Returns:
            ``True`` if the key has an expiration date that is in the past,
            ``False`` if the key has not expired or has no expiration set.

        Raises:
            AttributeError: If ``expires_at`` is not a datetime or ``None``.
        """
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    async def mark_used(self) -> None:
        """Record the current UTC time as the last usage timestamp.

        Updates the ``last_used_at`` field to ``datetime.now(timezone.utc)``
        and persists only that field to the database via a partial update.
        This allows callers to track when a key was most recently exercised
        without rewriting the entire row.

        Returns:
            None.

        Raises:
            tortoise.exceptions.OperationalError: If the database update fails
                due to a connection or integrity issue.
        """
        self.last_used_at = datetime.now(timezone.utc)
        await self.save(update_fields=["last_used_at"])

    async def revoke(self) -> None:
        """Deactivate this API key so it can no longer be used for authentication.

        Sets the ``is_active`` flag to ``False`` and persists only that field
        to the database. Once revoked, subsequent calls to
        :meth:`ApiKeyManager.verify` will reject this key.

        Returns:
            None.

        Raises:
            tortoise.exceptions.OperationalError: If the database update fails
                due to a connection or integrity issue.
        """
        self.is_active = False  # ty: ignore[invalid-assignment]
        await self.save(update_fields=["is_active"])


class ApiKeyManager:
    """High-level manager for creating, verifying, and revoking API keys.

    Provides an asynchronous interface over the :class:`ApiKey` model that
    encapsulates key generation, hash-based lookup, and bulk revocation
    logic. Instances of this class are intended to be long-lived and reused
    across multiple requests.

    Attributes:
        model: The :class:`ApiKey` Tortoise model class used for all
            database operations.
    """

    model = ApiKey

    async def create_key(
        self,
        user_id: int,
        name: str,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
        prefix: str = "sillo",
    ) -> tuple[str, ApiKey]:
        """Generate a new API key and persist it in the database.

        Delegates key generation to :func:`generate_api_key`, then creates a
        new :class:`ApiKey` row with the resulting hash. The plaintext key is
        returned to the caller exactly once; it is never stored.

        Args:
            user_id: The integer ID of the user who will own this key.
            name: A human-readable label for the key (e.g. ``"CI deploy"``).
            scopes: An optional list of permission scope strings to attach to
                the key. Defaults to an empty list when ``None``.
            expires_at: An optional UTC datetime after which the key is
                considered expired. ``None`` means the key never expires.
            prefix: The prefix prepended to the random token. Defaults to
                ``"sillo"``.

        Returns:
            A two-element tuple of ``(full_key, apikey)`` where ``full_key``
            is the plaintext key string and ``apikey`` is the persisted
            :class:`ApiKey` model instance.

        Raises:
            tortoise.exceptions.IntegrityError: If a key with the same hash
                already exists (extremely unlikely due to cryptographic
                randomness).
        """
        full_key, _, key_hash = generate_api_key(prefix=prefix)
        apikey = await self.model.create(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            scopes=scopes or [],
            expires_at=expires_at,
        )
        return full_key, apikey

    async def verify(self, raw_key: str) -> ApiKey | None:
        """Authenticate a raw API key and return the associated model instance.

        Hashes the provided key, looks it up among active keys, and checks
        whether it has expired. If the key is valid, its ``last_used_at``
        timestamp is updated before the instance is returned.

        Args:
            raw_key: The plaintext API key string to verify.

        Returns:
            The matching :class:`ApiKey` instance if the key is valid, active,
            and not expired; ``None`` otherwise.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection issue.
        """
        key_hash = hash_api_key(raw_key)
        apikey = await self.model.filter(key_hash=key_hash, is_active=True).first()
        if apikey is None or apikey.is_expired:
            return None
        await apikey.mark_used()
        return apikey

    async def get_for_user(self, user_id: int) -> list[ApiKey]:
        """Retrieve all active API keys belonging to a specific user.

        Queries the database for every :class:`ApiKey` row whose ``user_id``
        matches and whose ``is_active`` flag is ``True``. Expired keys that
        are still marked active are included in the result; callers should
        check :attr:`ApiKey.is_expired` if needed.

        Args:
            user_id: The integer ID of the user whose keys should be fetched.

        Returns:
            A list of active :class:`ApiKey` instances for the given user.
            The list is empty if the user has no active keys.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection issue.
        """
        return await self.model.filter(user_id=user_id, is_active=True).all()

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Revoke every active API key belonging to a specific user.

        Counts the number of currently active keys for the user, then
        performs a bulk update setting ``is_active`` to ``False`` on all
        of that user's keys (both active and already-inactive). Returns
        the count of keys that were active before the revocation.

        Args:
            user_id: The integer ID of the user whose keys should be revoked.

        Returns:
            The number of keys that were active before this call. A return
            value of ``0`` indicates the user had no active keys.

        Raises:
            tortoise.exceptions.OperationalError: If the database query or
                update fails due to a connection issue.
        """
        count = await self.model.filter(user_id=user_id, is_active=True).count()
        await self.model.filter(user_id=user_id).update(is_active=False)
        return count
