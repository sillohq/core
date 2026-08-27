import json
import os
import re
from typing import Any

from .base import BaseSessionInterface

#: The shape a session key must have before it is allowed anywhere near a
#: filesystem path.
#:
#: :meth:`BaseSessionInterface.generate_session_key` produces 64 hexadecimal
#: characters, which this matches. It is deliberately wider than that so a
#: project overriding the generator with another URL-safe token keeps working,
#: and deliberately excludes ``.`` and every separator, because those are the
#: only characters that let a key address a file outside the session
#: directory.
_SAFE_SESSION_KEY = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class FileSessionManager(BaseSessionInterface):
    """Filesessionmanager"""

    def __init__(self, config=None) -> None:
        """Init"""
        super().__init__(config)
        self.storage_path = getattr(config, "session_file_storage_path", "__sessions")

        if self.storage_path and not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)

    @staticmethod
    def is_valid_session_key(session_key: Any) -> bool:
        """Report whether *session_key* is safe to build a path from."""
        return isinstance(session_key, str) and bool(
            _SAFE_SESSION_KEY.fullmatch(session_key)
        )

    def create_session(self, session_key: str | None = None):
        """Build a session, refusing to carry forward an unusable key.

        The key arrives from a cookie, which is to say from whoever is making
        the request. A value that could not have been issued by this backend
        is treated as though no cookie had been sent at all, so the visitor
        simply gets a new session: that keeps a malformed or hostile cookie
        from reaching :meth:`_get_file_path`, and answers it with ordinary
        behaviour rather than an error a caller could use to probe the
        filesystem.
        """
        if session_key is not None and not self.is_valid_session_key(session_key):
            session_key = None

        return super().create_session(session_key)

    def _get_file_path(self, session_key: str) -> str:
        """Return the file backing *session_key*, refusing to leave the store.

        Two checks, because they fail differently. The pattern rejects keys
        that were never plausible; resolving the result and confirming it is
        still under ``storage_path`` catches whatever the pattern did not
        anticipate — a symlinked storage directory, say — and turns what would
        be an arbitrary file read or write into an exception.
        """
        if not self.is_valid_session_key(session_key):
            raise ValueError("Invalid session key")

        path = os.path.join(self.storage_path, f"{session_key}.json")

        root = os.path.realpath(self.storage_path)
        resolved = os.path.realpath(path)

        if os.path.dirname(resolved) != root:  # pragma: no cover
            # Defense in depth: _SAFE_SESSION_KEY already rejects any key
            # that could contain a path separator, so this only guards
            # against something the pattern did not anticipate (e.g. a
            # symlinked storage directory), not a reachable input.
            raise ValueError("Session key escapes the session directory")

        return path

    def _load_session_data(self, session_key: str) -> dict[str, Any] | None:
        """Load Session Data"""
        path = self._get_file_path(session_key)

        if os.path.exists(path):
            with open(path, "r") as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    return None

        return None

    def _save_session_data(self, session_key: str, data: dict[str, Any]) -> None:
        """Save Session Data"""
        path = self._get_file_path(session_key)

        with open(path, "w") as file:
            json.dump(data, file)

    def _delete_session_file(self, session_key: str) -> None:
        """Delete Session File"""
        path = self._get_file_path(session_key)

        if os.path.exists(path):
            os.remove(path)

    async def delete_key(self, session_key: str) -> None:
        """Remove the file backing *session_key*.

        Used when a session is rotated, to retire the record the previous
        cookie pointed at. An unusable key has no file to remove, so it is
        ignored rather than raised on — the caller is cleaning up, and there
        is nothing here to clean.
        """
        if not self.is_valid_session_key(session_key):
            return

        self._delete_session_file(session_key)

    async def load(self, session):
        """Load"""
        key = session.get_session_key()

        data = self._load_session_data(key)

        if data:
            session._session_cache.update(data)
        else:
            session._session_cache.clear()

    async def save(self, session):
        """Save"""
        key = session.get_session_key()

        if session.deleted:
            self._delete_session_file(key)
            session.session_key = None
            return ""

        self._save_session_data(key, session._session_cache)

        session.session_key = key

        return key
