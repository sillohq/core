from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sillo.auth.session_auth.models import Session


class SessionUserMixin:
    """Mixin that adds session management capabilities to a user model.

    Provides convenience methods for creating, querying, and terminating
    user sessions.  Designed to be mixed into a user model class that
    exposes an ``identity`` attribute representing the user's unique
    primary key.

    All methods operate on the ``Session`` model to persist and query
    session records associated with the mixed-in user instance.
    """

    async def create_session(
        self,
        session_key: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_name: Optional[str] = None,
        duration_seconds: int = 86400,
    ):
        """Create a new session record for this user.

        Persists a new ``Session`` row linked to the current user, with
        an expiration timestamp computed from the supplied duration.

        Args:
            session_key: A unique string token that identifies this
                session in the session store and database.
            ip_address: The IP address of the client that initiated
                the session, or ``None`` if not captured.
            user_agent: The raw User-Agent header string from the
                client request, or ``None`` if not captured.
            device_name: An optional human-readable label for the
                device or browser, or ``None`` if unspecified.
            duration_seconds: The number of seconds from now until
                the session expires.  Defaults to 86400 (24 hours).

        Returns:
            Session: The newly created ``Session`` model instance
            persisted to the database.

        Raises:
            ValueError: If the user's ``identity`` attribute cannot
            be converted to an integer for the foreign key lookup.
        """
        return await Session.create(
            user_id=int(str(self.identity)),
            session_key=session_key,
            ip_address=ip_address,
            user_agent=user_agent,
            device_name=device_name,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=duration_seconds),
        )

    async def get_active_sessions(self):
        """Retrieve all currently active and non-expired sessions for this user.

        Queries the ``Session`` table for records belonging to this
        user that are still marked as active and whose expiration
        timestamp is in the future.

        Args:
            None: Uses the user instance's ``identity`` attribute
            to scope the query automatically.

        Returns:
            list[Session]: A list of ``Session`` model instances
            representing the user's active sessions.  Returns an
            empty list when no active sessions exist.

        Raises:
            ValueError: If the user's ``identity`` attribute cannot
            be converted to an integer for the database query.
        """
        now = datetime.now(timezone.utc)
        return await Session.filter(
            user_id=int(str(self.identity)),
            is_active=True,
            expires_at__gt=now,
        ).all()

    async def logout_everywhere(self) -> int:
        """Terminate all active sessions for this user across all devices.

        Delegates to ``Session.terminate_all_for_user`` to deactivate
        every session record associated with this user's identity.

        Args:
            None: Uses the user instance's ``identity`` attribute
            to scope the termination query automatically.

        Returns:
            int: The number of session records that were terminated
            by this operation.

        Raises:
            ValueError: If the user's ``identity`` attribute cannot
            be converted to an integer for the database query.
        """
        return await Session.terminate_all_for_user(int(str(self.identity)))

    async def logout_session(self, session_key: str) -> bool:
        """Terminate a specific session identified by its session key.

        Looks up the session record matching both the current user's
        identity and the provided session key, then marks it as
        inactive if found.

        Args:
            session_key: The unique session token string identifying
                the specific session to terminate.

        Returns:
            bool: ``True`` if a matching active session was found
            and terminated; ``False`` if no matching session existed
            or it was already inactive.

        Raises:
            ValueError: If the user's ``identity`` attribute cannot
            be converted to an integer for the database query.
        """
        session = await Session.filter(
            user_id=int(str(self.identity)),
            session_key=session_key,
            is_active=True,
        ).first()
        if session:
            await session.terminate()
            return True
        return False

    async def active_session_count(self) -> int:
        """Return the number of currently active and non-expired sessions.

        Counts session records belonging to this user that are still
        marked as active and whose expiration timestamp is in the
        future.

        Args:
            None: Uses the user instance's ``identity`` attribute
            to scope the count query automatically.

        Returns:
            int: The number of active, non-expired sessions for this
            user.  Returns 0 when no such sessions exist.

        Raises:
            ValueError: If the user's ``identity`` attribute cannot
            be converted to an integer for the database query.
        """
        now = datetime.now(timezone.utc)
        return await Session.filter(
            user_id=int(str(self.identity)),
            is_active=True,
            expires_at__gt=now,
        ).count()
