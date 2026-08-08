import typing
from typing import Any

from sillo.core.http import Request, Response
from sillo.middleware.base import BaseMiddleware
from sillo.session.session_objects import Session

from .base import BaseSessionInterface
from .config import SessionConfig, reject_unknown_settings
from .signed_cookies import SignedSessionManager


class SessionMiddleware(BaseMiddleware):
    """Sessionmiddleware"""

    def __init__(
        self,
        config: SessionConfig | None = None,
        manager: BaseSessionInterface | None = None,
        secret_key: str | None = None,
        **settings: Any,
    ):
        """Install session handling.

        Settings may be given either as a :class:`SessionConfig` or as keyword
        arguments here, which is the shorter form and what most applications
        want::

            app.use(SessionMiddleware(secret_key=..., session_cookie_secure=False))
            app.use(SessionMiddleware(config=SessionConfig(...), secret_key=...))

        Args:
            config: A prepared configuration. Cannot be combined with keyword
                settings, since one of the two would have to win silently.
            manager: A session interface to use instead of the signed-cookie
                default.
            secret_key: Key the default backend signs the cookie with.
            **settings: Any setting :class:`SessionConfig` accepts.

        Raises:
            TypeError: If given a name that is not a session setting, or if
                ``config`` is combined with keyword settings.
        """
        # These used to go to super().__init__(**kwargs), which accepts anything
        # and reads none of it — so the documented setup, which passes settings
        # here rather than through a SessionConfig, configured nothing at all
        # beyond the secret key.
        reject_unknown_settings(settings, called="SessionMiddleware()")

        if config is not None and settings:
            raise TypeError(
                "SessionMiddleware() got both a config= and the settings "
                f"{', '.join(sorted(settings))}. Pass one or the other: "
                "settings given here would otherwise have to either override "
                "the config or be dropped, and both are surprising."
            )

        super().__init__()

        self.session_config = config or SessionConfig(**settings)

        # A manager given here wins, then one carried on the config — which was
        # a documented setting that nothing read — and finally the signed-cookie
        # default.
        chosen = manager if manager is not None else self.session_config.manager

        if isinstance(chosen, type):
            raise TypeError(
                f"manager must be an instance, not the class {chosen.__name__}. "
                f"A backend is configured — it needs to know where to store "
                f"sessions — so build it first:\n\n"
                f"    config = SessionConfig(...)\n"
                f"    SessionMiddleware(config=config, manager={chosen.__name__}(config), ...)\n"
            )

        self.session_interface = (
            chosen
            if chosen is not None
            else SignedSessionManager(secret_key=secret_key)
        )

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ):
        """Process Request"""
        cookie_name = self.session_config.session_cookie_name or "session_id"
        session_key = request.cookies.get(cookie_name)

        session = self.session_interface.create_session(session_key)
        await session.load()

        request.scope["session"] = session

        return await call_next()

    async def process_response(self, request: Request, response: Response):
        """Process Response"""
        session: Session | None = request.scope.get("session")
        if session is None:
            return

        cookie_name = self.session_config.session_cookie_name or "session_id"

        if session.is_empty() and session.accessed:
            if session.modified:
                # Hand the emptied session to the backend before dropping the
                # cookie. Server-backed stores purge their record here; without
                # it the key stays valid for anyone who kept a copy of the
                # cookie, so logging out would only clear the browser's copy.
                await session.save()
            response.delete_cookie(key=cookie_name)
            return

        if session.should_set_cookie:
            value = await session.save()

            response.set_cookie(
                key=cookie_name,
                value=value,
                domain=self.session_config.session_cookie_domain,
                path=self.session_config.session_cookie_path or "/",
                httponly=self.session_config.session_cookie_httponly,
                secure=self.session_config.session_cookie_secure,
                samesite=self.session_config.session_cookie_samesite,
                expires=session.get_expiration_time(),
            )
