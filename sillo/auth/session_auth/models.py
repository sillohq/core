from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tortoise import fields

from sillo.record import Model, TimestampsMixin


class Session(Model, TimestampsMixin):
    """Active session tracking — per-user, per-device.

    Enables "logout everywhere" and session audit.  Each row represents
    a single authenticated session tied to a specific user and device.
    Sessions carry metadata such as IP address, user agent, and device
    name to support security auditing and device management features.

    The model supports soft-termination via the ``is_active`` flag and
    automatic expiration via the ``expires_at`` timestamp, allowing
    both explicit logout flows and time-based session invalidation.
    """

    id = fields.IntField(pk=True)
    user_id = fields.IntField(index=True)
    session_key = fields.CharField(max_length=255, unique=True, index=True)
    ip_address = fields.CharField(max_length=45, null=True, default=None)
    user_agent = fields.TextField(null=True, default=None)
    last_activity = fields.DatetimeField(auto_now=True)
    expires_at = fields.DatetimeField()
    is_active = fields.BooleanField(default=True)
    device_name = fields.CharField(max_length=255, null=True, default=None)

    class Meta:
        """Tortoise ORM meta configuration for the Session model.

        Specifies the physical database table name and any additional
        ORM-level configuration for query generation and migrations.

        Attributes:
            table: The name of the database table where session
                records are persisted.
        """

        table = "user_sessions"

    @property
    def is_expired(self) -> bool:
        """Check whether this session has passed its expiration time.

        Compares the current UTC time against the session's
        ``expires_at`` timestamp to determine if the session is
        no longer valid.

        Args:
            None: Operates on the instance's own ``expires_at``
            attribute directly.

        Returns:
            bool: ``True`` if the current UTC time is later than
            the session's expiration timestamp; ``False`` if the
            session is still within its valid time window.

        Raises:
            None: No exceptions are raised under normal operation.
        """
        return datetime.now(timezone.utc) > self.expires_at

    async def mark_activity(self) -> None:
        """Update the last-activity timestamp to the current UTC time.

        Sets ``last_activity`` to ``datetime.now(timezone.utc)`` and
        persists only that field to the database, providing an
        efficient heartbeat mechanism for session liveness tracking.

        Args:
            None: Operates on the instance's own fields and persists
            the update via the ORM save mechanism.

        Returns:
            None

        Raises:
            None: Database errors from the underlying ORM save
            operation propagate to the caller unchanged.
        """
        self.last_activity = datetime.now(timezone.utc)
        await self.save(update_fields=["last_activity"])

    async def terminate(self) -> None:
        """Soft-terminate this session by marking it as inactive.

        Sets the ``is_active`` flag to ``False`` and persists only
        that field to the database.  The session row is retained
        for audit purposes but will no longer be considered valid
        by authentication checks.

        Args:
            None: Operates on the instance's own fields and persists
            the update via the ORM save mechanism.

        Returns:
            None

        Raises:
            None: Database errors from the underlying ORM save
            operation propagate to the caller unchanged.
        """
        self.is_active = False  # ty: ignore[invalid-assignment]
        await self.save(update_fields=["is_active"])

    async def extend(self, duration_seconds: int = 3600) -> None:
        """Extend the session expiration by a given number of seconds.

        Recalculates ``expires_at`` as the current UTC timestamp plus
        the specified duration and persists the updated value to the
        database.

        Args:
            duration_seconds: The number of seconds from the current
                time to set as the new expiration.  Defaults to 3600
                (one hour).

        Returns:
            None

        Raises:
            None: Database errors from the underlying ORM save
            operation propagate to the caller unchanged.
        """
        # `expires_at` is a DatetimeField. Assigning `.timestamp() + seconds`
        # put a float there, which the database layer rejected and which made
        # `is_expired` raise when it compared a datetime against it.
        self.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=duration_seconds
        )
        await self.save(update_fields=["expires_at"])

    @classmethod
    async def terminate_all_for_user(cls, user_id: int) -> int:
        """Terminate all active sessions for a given user.

        Counts the number of currently active sessions for the
        specified user, then deactivates all of that user's sessions
        regardless of their current active state.

        Args:
            user_id: The integer primary key of the user whose
                sessions should all be terminated.

        Returns:
            int: The number of active sessions that were terminated
            by this operation.  Returns 0 if the user had no active
            sessions at the time of the call.

        Raises:
            None: Database errors from the underlying ORM filter
            and update operations propagate to the caller unchanged.
        """
        count = await cls.filter(user_id=user_id, is_active=True).count()
        await cls.filter(user_id=user_id).update(is_active=False)
        return count

    @classmethod
    async def cleanup_expired(cls) -> int:
        """Deactivate all sessions that have passed their expiration time.

        Queries for all sessions that are still marked as active but
        whose ``expires_at`` timestamp is in the past, then iterates
        through them to set ``is_active`` to ``False`` individually.

        Args:
            None: This class method operates on the database directly
            without requiring an instance reference.

        Returns:
            int: The number of expired sessions that were deactivated
            by this cleanup run.  Returns 0 if no expired sessions
            were found.

        Raises:
            None: Database errors from the underlying ORM filter
            and save operations propagate to the caller unchanged.
        """
        now = datetime.now(timezone.utc)
        expired = await cls.filter(is_active=True, expires_at__lt=now).all()
        for session in expired:
            session.is_active = False  # ty: ignore[invalid-assignment]
            await session.save(update_fields=["is_active"])
        return len(expired)
