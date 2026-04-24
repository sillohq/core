import typing
import warnings
from typing import Any, Optional

from nexios.config import get_config
from nexios.http import Request, Response
from nexios.middleware.base import BaseMiddleware

from .base import BaseSessionInterface
from .config import SessionConfig
from .signed_cookies import SignedSessionManager


class SessionMiddleware(BaseMiddleware):
    def __init__(
        self,
        config: Optional[SessionConfig] = None,
        manager: Optional[BaseSessionInterface] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.manager = manager

        if config is not None:
            if not isinstance(config, SessionConfig):
                raise TypeError("config must be a SessionConfig instance")
            self.session_config = config
        else:
            warnings.warn(
                "Using get_config() for Session middleware is deprecated. "
                "Please pass SessionConfig directly to SessionMiddleware constructor.",
                DeprecationWarning,
                stacklevel=2,
            )

    def get_manager(self):
        if self.manager:
            return self.manager
        if not hasattr(self, "session_config") or not self.session_config:
            return SignedSessionManager
        else:
            return self.session_config.manager or SignedSessionManager

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ):
        if hasattr(self, "session_config") and self.session_config:
            session_cfg = self.session_config
            try:
                self.secret = get_config().secret_key
            except RuntimeError:
                self.secret = None
        else:
            try:
                app_config = get_config()
                self.secret = app_config.secret_key
                session_cfg = app_config.session
            except RuntimeError:
                self.secret = None
                session_cfg = None

        if not self.secret:
            return await call_next()

        if session_cfg:
            session_cookie_name = session_cfg.session_cookie_name or "session_id"
        else:
            session_cookie_name = "session_id"

        self.session_cookie_name = session_cookie_name
        manager = self.get_manager()
        session: type[BaseSessionInterface] = manager(
            session_key=request.cookies.get(session_cookie_name)
        )
        await session.load()
        request.scope["session"] = session
        return await call_next()

    async def process_response(self, request: Request, response: Response):
        if not self.secret:
            return
        if request.session.is_empty() and request.session.accessed:
            response.delete_cookie(key=self.session_cookie_name)
            return

        if request.session.should_set_cookie:
            await request.session.save()

            session_key = request.session.get_session_key()
            response.set_cookie(
                key=self.session_cookie_name,
                value=session_key,
                domain=request.session.get_cookie_domain(),
                path=request.session.get_cookie_path() or "/",
                httponly=request.session.get_cookie_httponly() or False,
                secure=request.session.get_cookie_secure() or False,
                samesite=request.session.get_cookie_samesite() or "lax",
                expires=request.session.get_expiration_time(),
            )
