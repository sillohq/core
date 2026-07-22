import secrets
from typing import Optional

from .session_objects import Session


class BaseSessionInterface:
    """Basesessioninterface

        Returns:
            [description]

        Raises:
            [description]
    """
    def __init__(self, config=None) -> None:
        """Init

            Args:
                config: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        self.config = config

    def generate_session_key(self) -> str:
        """Generate Session Key

            Returns:
                [description]

            Raises:
                [description]
        """
        return secrets.token_hex(32)

    def create_session(self, session_key: Optional[str] = None):
        """Create Session

            Args:
                session_key: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return Session(self, session_key)

    async def load(self, session):
        """Load

            Args:
                session: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        raise NotImplementedError

    async def save(self, session):
        """Save

            Args:
                session: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        raise NotImplementedError

    def get_cookie_name(self) -> str:
        """Get Cookie Name

            Returns:
                [description]

            Raises:
                [description]
        """
        if not self.config:
            return "session_id"
        return getattr(self.config, "session_cookie_name", "session_id")

    def get_cookie_domain(self):
        """Get Cookie Domain

            Returns:
                [description]

            Raises:
                [description]
        """
        if not self.config:
            return None
        return getattr(self.config, "session_cookie_domain", None)

    def get_cookie_path(self):
        """Get Cookie Path

            Returns:
                [description]

            Raises:
                [description]
        """
        if not self.config:
            return "/"
        return getattr(self.config, "session_cookie_path", "/")

    def get_cookie_httponly(self):
        """Get Cookie Httponly

            Returns:
                [description]

            Raises:
                [description]
        """
        if not self.config:
            return True
        return getattr(self.config, "session_cookie_httponly", True)

    def get_cookie_secure(self):
        """Get Cookie Secure

            Returns:
                [description]

            Raises:
                [description]
        """
        if not self.config:
            return False
        return getattr(self.config, "session_cookie_secure", False)

    def get_cookie_samesite(self):
        """Get Cookie Samesite

            Returns:
                [description]

            Raises:
                [description]
        """
        if not self.config:
            return "lax"
        return getattr(self.config, "session_cookie_samesite", "lax")
