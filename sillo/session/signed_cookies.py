import typing
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .base import BaseSessionInterface


class SignedSessionManager(BaseSessionInterface):
    """Signedsessionmanager

    Returns:
        [description]

    Raises:
        [description]
    """

    def __init__(self, config=None, secret_key: typing.Optional[str] = None):
        """Init

        Args:
            config: [description]
            secret_key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        super().__init__(config)

        if not secret_key:
            raise RuntimeError("secret_key is required for signed sessions")

        self.serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt="nexio.session.signed_cookie",
        )

    def sign_session_data(self, session_data: typing.Dict[str, typing.Any]) -> str:
        """Sign Session Data

        Args:
            session_data: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.serializer.dumps(session_data)

    def verify_session_data(self, token: str | None) -> typing.Dict[str, typing.Any]:
        """Verify Session Data

        Args:
            token: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if not token:
            return {}

        try:
            return self.serializer.loads(token)
        except BadSignature:
            return {}

    async def load(self, session):
        """Load

        Args:
            session: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        token = session.session_key

        data = self.verify_session_data(token)

        if data:
            session._session_cache.update(data)
        else:
            session._session_cache.clear()

    async def save(self, session):
        """Save

        Args:
            session: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if session.deleted:
            session.session_key = ""
            return ""

        signed = self.sign_session_data(session._session_cache)
        session.session_key = signed

        return signed
