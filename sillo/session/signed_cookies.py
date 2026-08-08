import typing

from itsdangerous import BadSignature, URLSafeTimedSerializer

from .base import BaseSessionInterface


class SignedSessionManager(BaseSessionInterface):
    """Signedsessionmanager"""

    def __init__(self, config=None, secret_key: str | None = None):
        """Init"""
        super().__init__(config)

        if not secret_key:
            raise RuntimeError("secret_key is required for signed sessions")

        self.serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt="nexio.session.signed_cookie",
        )

    def sign_session_data(self, session_data: dict[str, typing.Any]) -> str:
        """Sign Session Data"""
        return self.serializer.dumps(session_data)

    def verify_session_data(self, token: str | None) -> dict[str, typing.Any]:
        """Verify Session Data"""
        if not token:
            return {}

        try:
            return self.serializer.loads(token)
        except BadSignature:
            return {}

    async def load(self, session):
        """Load"""
        token = session.session_key

        data = self.verify_session_data(token)

        if data:
            session._session_cache.update(data)
        else:
            session._session_cache.clear()

    async def save(self, session):
        """Save"""
        if session.deleted:
            session.session_key = ""
            return ""

        signed = self.sign_session_data(session._session_cache)
        session.session_key = signed

        return signed
