import typing

from sillo.helpers.signing import BadSignature, URLSafeTimedSerializer

from .base import BaseSessionInterface
from .config import resolve_session_config

#: How long a signed session cookie stays valid when nothing configures it.
#: Matches ``SessionConfig.session_expiration_time``.
DEFAULT_MAX_AGE = 86400


class SignedSessionManager(BaseSessionInterface):
    """Keep the whole session inside a signed cookie, with no server-side store.

    The cookie carries the session's data, signed so it cannot be edited, and
    stamped so it cannot be used forever. It is **signed, not encrypted** —
    whoever holds the cookie can base64-decode it and read every key in the
    session. Put identifiers in it, not secrets.

    Because there is nothing stored server-side, a token stays valid for its
    whole lifetime no matter what happens to the session it came from: signing
    out clears the browser's copy but cannot revoke a copy someone else kept.
    That is the trade this backend makes, and ``max_age`` is the only thing
    bounding it — which is why it is always set.
    """

    def __init__(
        self,
        config=None,
        secret_key: str | None = None,
        max_age: int | None = None,
    ):
        """Init

        Args:
            config: Session settings, either a
                :class:`~sillo.session.config.SessionConfig` or an application
                config carrying one as ``.session``.
            secret_key: The key the cookie is signed with.
            max_age: How many seconds a signed cookie stays valid, overriding
                ``session_expiration_time``.

        Raises:
            RuntimeError: If no ``secret_key`` is given.
        """
        super().__init__(config)

        if not secret_key:
            raise RuntimeError("secret_key is required for signed sessions")

        settings = resolve_session_config(config)

        if max_age is None:
            max_age = (
                getattr(settings, "session_expiration_time", None) if settings else None
            ) or DEFAULT_MAX_AGE

        #: Bound in the signature rather than only on the cookie. The
        #: ``Expires`` attribute is a request to the browser and nothing more;
        #: anyone replaying a captured cookie simply does not honour it.
        self.max_age = max_age

        self.serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt="sillo.session.signed_cookie",
        )

    def sign_session_data(self, session_data: dict[str, typing.Any]) -> str:
        """Sign Session Data"""
        return self.serializer.dumps(session_data)

    def verify_session_data(self, token: str | None) -> dict[str, typing.Any]:
        """Verify Session Data

        A token that is missing, tampered with, or older than :attr:`max_age`
        all mean the same thing to a caller — there is no session here — so
        each yields an empty dict rather than an error.
        """
        if not token:
            return {}

        try:
            data = self.serializer.loads(token, max_age=self.max_age)
        except BadSignature:
            return {}

        # A signed payload that is not an object would reach `update()` below
        # and raise. Nothing this class writes produces one, but the check
        # costs nothing and keeps a key rotated onto an older format from
        # turning into a 500.
        return data if isinstance(data, dict) else {}

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
