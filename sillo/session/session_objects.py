from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import resolve_session_config


class Session:
    """The per-request session, reached as ``request.session``.

    Behaves like a dictionary. Reads and writes go to an in-memory copy of the
    session data; the backend is only touched by :meth:`load`, which the
    middleware calls before the handler runs, and :meth:`save`, which it calls
    afterwards.

    Three flags drive that: ``accessed`` records that something looked at the
    session, ``modified`` that something changed it, and ``deleted`` that
    something removed a key. The middleware reads them to decide whether to
    write a cookie at all, so a request that never touches the session costs
    nothing beyond loading it.

    Example:
        ```python
        @app.get("/")
        async def index(ctx):
            count = request.session.get("count", 0) + 1
            request.session["count"] = count
            return text(f"seen you {count} times")
        ```
    """

    def __init__(self, interface, session_key: str | None = None) -> None:
        """Bind a session to the backend that will load and store it.

        Args:
            interface: The session backend — a
                :class:`~sillo.session.base.BaseSessionInterface` — that knows
                how to read and write this session's data.
            session_key: The key from the request's cookie, or ``None`` for a
                visitor who does not have one yet.
        """
        self.interface = interface
        self.session_key = session_key
        self._session_cache: dict[str, Any] = {}

        self.modified = False
        self.accessed = False
        self.deleted = False

        #: Set by :meth:`cycle_key` to the identifier this session had before
        #: it was rotated, so that :meth:`save` can purge the old record from
        #: the backend once the new one is written.
        self._retired_session_key: str | None = None

        self._expiration_time: datetime | None = None

    def __getitem__(self, key: str) -> Any:
        """Return a value, raising if it is not there.

        Args:
            key: The key to look up.

        Returns:
            The stored value.

        Raises:
            KeyError: If the key is not in the session. Use :meth:`get` for a
                default instead.
        """
        self.accessed = True
        return self._session_cache[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Store a value, marking the session for saving.

        Args:
            key: The key to store under.
            value: The value to store. It has to survive the backend's
                serialization — JSON for the signed-cookie backend, so plain
                data rather than arbitrary objects.
        """
        self.modified = True
        self.accessed = True
        self._session_cache[key] = value

    def __delitem__(self, key: str) -> None:
        """Remove a key, marking the session for saving.

        Args:
            key: The key to remove.

        Raises:
            KeyError: If the key is not in the session. Use :meth:`delete` to
                remove a key that may be absent.
        """
        # Not ``deleted``: that flag means "purge this session", which is what
        # a backend acts on. Removing one key leaves a session that still
        # exists and must still be stored.
        self.modified = True
        self.accessed = True
        del self._session_cache[key]

    def __contains__(self, key: str) -> bool:
        """Report whether a key is in the session.

        Args:
            key: The key to test.

        Returns:
            ``True`` if present.
        """
        self.accessed = True
        return key in self._session_cache

    def __len__(self) -> int:
        """Return how many keys the session holds."""
        self.accessed = True
        return len(self._session_cache)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a value, or a default when it is absent.

        Args:
            key: The key to look up.
            default: What to return when the key is not there.

        Returns:
            The stored value, or ``default``.
        """
        self.accessed = True
        return self._session_cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a value. The method form of ``session[key] = value``.

        Args:
            key: The key to store under.
            value: The value to store.
        """
        self.modified = True
        self.accessed = True
        self._session_cache[key] = value

    def delete(self, key: str) -> None:
        """Remove a key if it is present, without raising when it is not.

        Args:
            key: The key to remove.
        """
        # See __delitem__: removing a key is not deleting the session.
        self.modified = True
        self.accessed = True
        if key in self._session_cache:
            del self._session_cache[key]

    def clear(self) -> None:
        """Remove everything from the session.

        This is what logging out should call: the middleware sees an empty,
        modified session, hands it to the backend so a server-side store can
        purge its record, and drops the cookie.
        """
        self.accessed = True
        self.modified = True
        self.deleted = True
        self._session_cache.clear()

    def keys(self):
        """Return a view of the session's keys."""
        self.accessed = True
        return self._session_cache.keys()

    def values(self):
        """Return a view of the session's values."""
        self.accessed = True
        return self._session_cache.values()

    def items(self):
        """Return a view of the session's key/value pairs."""
        self.accessed = True
        return self._session_cache.items()

    def is_empty(self) -> bool:
        """Report whether the session holds nothing.

        Returns:
            ``True`` when there are no keys.
        """
        return len(self._session_cache) == 0

    def update(self, other: dict[str, Any]):
        """Merge a dictionary into the session.

        Args:
            other: Keys and values to write. Existing keys are overwritten.
        """
        self.modified = True
        self._session_cache.update(other)

    def get_session_key(self) -> str:
        """Return this session's key, generating one if it has none.

        Returns:
            The key from the request's cookie, or a freshly generated key for
            a visitor arriving without one.
        """
        if self.session_key:
            return self.session_key
        return self.interface.generate_session_key()

    def set_expiration_time(self, expiration: datetime) -> None:
        """Override when this session expires.

        Args:
            expiration: An aware ``datetime`` at which the cookie should
                expire, overriding whatever the configuration would give it.
        """
        self._expiration_time = expiration

    def get_expiration_time(self) -> datetime | None:
        """Return when this session's cookie expires.

        Uses an explicit :meth:`set_expiration_time` if one was given.
        Otherwise it comes from the configuration:

        * a permanent session — the default — expires
          ``session_expiration_time`` seconds from now;
        * a non-permanent one returns ``None``, so the cookie goes out with no
          ``Expires`` at all and the browser drops it when it closes, which is
          what "not permanent" says.

        This used to be the other way round: a permanent session got
        ``datetime.max``, so the default configuration issued a cookie that
        never expired, and ``session_expiration_time`` only applied to the
        non-permanent case that did not need it.

        Returns:
            An aware ``datetime``, or ``None`` for a browser-session cookie.
            Aware because :meth:`has_expired` compares against an aware
            ``now``, and a naive value made that raise ``TypeError`` instead
            of answering.
        """
        if self._expiration_time:
            return self._expiration_time

        settings = resolve_session_config(getattr(self.interface, "config", None))

        permanent = getattr(settings, "session_permanent", True) if settings else True
        seconds = (
            getattr(settings, "session_expiration_time", None) if settings else None
        ) or 86400

        if not permanent:
            return None

        self._expiration_time = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        return self._expiration_time

    def has_expired(self) -> bool:
        """Report whether this session's expiry has passed.

        Returns:
            ``True`` when the expiry is in the past.
        """
        expiration_time = self.get_expiration_time()
        return bool(expiration_time and datetime.now(timezone.utc) > expiration_time)

    @property
    def should_set_cookie(self) -> bool:
        """Whether the response should carry a session cookie.

        Always true when the session changed. Also true on every response when
        the session is permanent and ``session_refresh_each_request`` is set,
        which is what slides the expiry forward for an active visitor.
        """
        settings = resolve_session_config(getattr(self.interface, "config", None))

        if settings is None:
            return self.modified

        return self.modified or (
            settings.session_permanent and settings.session_refresh_each_request
        )

    async def load(self) -> None:
        """Populate this session from the backend.

        Called by the middleware before the handler runs. A key that is
        unknown, expired or tampered with leaves the session empty rather
        than raising.
        """
        return await self.interface.load(self)

    def cycle_key(self) -> None:
        """Give this session a new identifier, keeping its contents.

        Call this whenever the trust level of a session changes — logging in
        above all. Without it a session identifier that was known before
        authentication is still valid after it, so anyone who planted or
        observed that identifier inherits the authenticated session. That is
        session fixation, and rotating the key is the whole defence.

        The rotation is applied when the session is next saved: the new record
        is written first and only then is the old one purged, so a failure
        part-way through leaves a session that still works rather than one
        that has been dropped from under a signed-in user.

        Backends whose cookie carries the session's whole contents rather than
        a pointer to it — the signed-cookie default — re-sign on save and so
        change their cookie value regardless of what this sets.
        """
        if self.session_key is not None and self._retired_session_key is None:
            self._retired_session_key = self.session_key

        self.session_key = self.interface.generate_session_key()
        self.modified = True
        self.accessed = True

    async def save(self) -> str:
        """Write this session to the backend and return its cookie value.

        Clears ``modified``, ``deleted`` and ``accessed`` once the backend has
        been given the session, so a session saved twice in one request does
        not write twice. The flags are cleared *after* the backend runs and
        not before: they are part of what it is handed, and a store reading
        ``deleted`` off a session whose flags had already been reset would
        never see a deletion at all.

        Returns:
            The value to put in the session cookie — the session key for a
            server-side store, or the whole signed payload for the
            signed-cookie backend.
        """
        retired = self._retired_session_key
        self._retired_session_key = None

        value = await self.interface.save(self)

        if retired is not None and retired != self.session_key:
            await self.interface.delete_key(retired)

        self.modified = False
        self.deleted = False
        self.accessed = False

        return value

    def __str__(self) -> str:
        """Return the session's contents, for logging and debugging."""
        return f"<Session {self._session_cache}>"

    def __iter__(self) -> Iterator[str]:
        """Iterate over the session's keys."""
        self.accessed = True
        return iter(self._session_cache)

    def __repr__(self) -> str:
        """Return the session's key and contents, for logging and debugging."""
        return f"<Session {self.session_key} {self._session_cache}>"
