import typing
import warnings
from typing import Any

from sillo.core.http import Request, Response
from sillo.middleware.base import BaseMiddleware
from sillo.session.session_objects import Session

from .base import BaseSessionInterface
from .config import SessionConfig, reject_unknown_settings
from .signed_cookies import SignedSessionManager

#: What browsers will keep for one cookie, name and attributes included.
_COOKIE_LIMIT = 4096

#: Rough room for ``Path``, ``Expires``, ``SameSite`` and the rest, so the
#: warning fires slightly early rather than slightly late.
_COOKIE_ATTRIBUTE_ALLOWANCE = 128


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

        # The config has to be handed over, not just held here. Without it the
        # backend has no lifetime to bound its signed cookie with, and
        # `Session` finds no settings to read — so `session_expiration_time`,
        # `session_permanent` and `session_refresh_each_request` all did
        # nothing at all.
        self.session_interface = (
            chosen
            if chosen is not None
            else SignedSessionManager(
                config=self.session_config, secret_key=secret_key
            )
        )

        if getattr(self.session_interface, "config", None) is None:
            try:
                self.session_interface.config = self.session_config
            except AttributeError:
                # A backend that will not take one keeps its own defaults;
                # filling the gap is a convenience, not a requirement.
                pass

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
            # The attributes have to match the ones the cookie was set with, or
            # the browser will not accept the deletion — a `__Host-`-prefixed
            # session cookie is rejected outright when the deletion is not
            # marked Secure, and signing out leaves the cookie in place.
            response.delete_cookie(
                key=cookie_name,
                path=self.session_config.session_cookie_path or "/",
                domain=self.session_config.session_cookie_domain,
                secure=self.session_config.session_cookie_secure,
                httponly=self.session_config.session_cookie_httponly,
                samesite=self.session_config.session_cookie_samesite,
            )
            return

        if session.should_set_cookie:
            value = await session.save()

            self._warn_if_oversized(cookie_name, value)

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

    @staticmethod
    def _warn_if_oversized(cookie_name: str, value: str) -> None:
        """Warn when a cookie is too large for browsers to keep.

        Browsers cap a cookie at roughly 4096 bytes including its name and
        attributes, and they do not report the ones they drop. For the
        signed-cookie backend, where the session *is* the cookie, that turns
        writing a little too much into a session that silently stops
        persisting — with a working response and nothing in the log.
        """
        if len(cookie_name) + len(value) + _COOKIE_ATTRIBUTE_ALLOWANCE <= _COOKIE_LIMIT:
            return

        warnings.warn(
            f"Session cookie {cookie_name!r} is {len(value)} bytes, over the "
            f"~{_COOKIE_LIMIT} byte limit browsers enforce. It will be dropped "
            f"silently, and the session will not persist. Store an identifier "
            f"in the session and the data behind a server-side backend.",
            RuntimeWarning,
            stacklevel=2,
        )
