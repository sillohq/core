import secrets
from typing import Optional

from .session_objects import Session


class BaseSessionInterface:
    def __init__(self, config=None) -> None:
        self.config = config

    def generate_session_key(self) -> str:
        return secrets.token_hex(32)

    def create_session(self, session_key: Optional[str] = None):
        return Session(self, session_key)

    async def load(self, session):
        raise NotImplementedError

    async def save(self, session):
        raise NotImplementedError

    def get_cookie_name(self) -> str:
        if not self.config:
            return "session_id"
        return getattr(self.config, "session_cookie_name", "session_id")

    def get_cookie_domain(self):
        if not self.config:
            return None
        return getattr(self.config, "session_cookie_domain", None)

    def get_cookie_path(self):
        if not self.config:
            return "/"
        return getattr(self.config, "session_cookie_path", "/")

    def get_cookie_httponly(self):
        if not self.config:
            return True
        return getattr(self.config, "session_cookie_httponly", True)

    def get_cookie_secure(self):
        if not self.config:
            return False
        return getattr(self.config, "session_cookie_secure", False)

    def get_cookie_samesite(self):
        if not self.config:
            return "lax"
        return getattr(self.config, "session_cookie_samesite", "lax")
