import secrets

from .session_objects import Session


class BaseSessionInterface:
    """Basesessioninterface"""

    def __init__(self, config=None) -> None:
        """Init"""
        self.config = config

    def generate_session_key(self) -> str:
        """Generate Session Key"""
        return secrets.token_hex(32)

    def create_session(self, session_key: str | None = None):
        """Create Session"""
        return Session(self, session_key)

    async def load(self, session):
        """Load"""
        raise NotImplementedError

    async def save(self, session):
        """Save"""
        raise NotImplementedError

    async def delete_key(self, session_key: str) -> None:
        """Purge a stored session by key, if this backend stores anything.

        Called by :meth:`Session.save` after a rotated session has been
        written under its new key, so that the record the old cookie pointed
        at stops being usable.

        The default does nothing, which is correct for any backend that keeps
        no server-side record — the signed-cookie manager holds the session in
        the cookie itself, so there is nothing to purge. Server-side stores
        must override it or a rotated key stays live in storage.
        """

    def get_cookie_name(self) -> str:
        """Get Cookie Name"""
        if not self.config:
            return "session_id"
        return getattr(self.config, "session_cookie_name", "session_id")

    def get_cookie_domain(self):
        """Get Cookie Domain"""
        if not self.config:
            return None
        return getattr(self.config, "session_cookie_domain", None)

    def get_cookie_path(self):
        """Get Cookie Path"""
        if not self.config:
            return "/"
        return getattr(self.config, "session_cookie_path", "/")

    def get_cookie_httponly(self):
        """Get Cookie Httponly"""
        if not self.config:
            return True
        return getattr(self.config, "session_cookie_httponly", True)

    def get_cookie_secure(self):
        """Get Cookie Secure"""
        if not self.config:
            return False
        return getattr(self.config, "session_cookie_secure", False)

    def get_cookie_samesite(self):
        """Get Cookie Samesite"""
        if not self.config:
            return "lax"
        return getattr(self.config, "session_cookie_samesite", "lax")
