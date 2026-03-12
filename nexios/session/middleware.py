import typing
import warnings
from typing import Any, Dict, Optional, Union

from nexios.config import get_config
from nexios.config.base import MakeConfig
from nexios.http import Request, Response
from nexios.middleware.base import BaseMiddleware

from .base import BaseSessionInterface
from .signed_cookies import SignedSessionManager


class SessionMiddleware(BaseMiddleware):
    def __init__(
        self, config: Optional[Union[MakeConfig, Dict[str, Any]]] = None, **kwargs: Any
    ):
        super().__init__(**kwargs)

        # Handle config parameter (new approach)
        if config is not None:
            if isinstance(config, MakeConfig):
                self.config = config
            elif isinstance(config, dict):
                self.config = MakeConfig(config)
            else:
                raise TypeError("config must be a MakeConfig instance or dictionary")
        else:
            # Fallback to get_config() (old approach) with warning
            warnings.warn(
                "Using get_config() for Session middleware is deprecated. "
                "Please pass config directly to SessionMiddleware constructor.",
                DeprecationWarning,
                stacklevel=2,
            )
            # Will be set in process_request

    def get_manager(self):
        if not hasattr(self, "config") or not self.config:
            return SignedSessionManager
        else:
            return getattr(self.config, "manager", None) or SignedSessionManager

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ):
        # Use config from __init__ if available, otherwise fallback to get_config()
        if hasattr(self, "config") and self.config:
            # Use provided config
            app_config = self.config
            # Get secret key from config or fallback
            if hasattr(app_config, "secret_key") and app_config.secret_key:
                self.secret = app_config.secret_key
            else:
                # Try to get from global config
                try:
                    self.secret = get_config().secret_key
                except RuntimeError:
                    self.secret = None
            # Get session config
            if hasattr(app_config, "session") and app_config.session:
                self.config = app_config.session
            else:
                # Try to get from global config
                try:
                    self.config = get_config().session
                except RuntimeError:
                    self.config = None
        else:
            # Fallback to get_config() (old approach)
            self.secret = get_config().secret_key
            self.config = get_config().session

        if not self.secret:
            return await call_next()

        if self.config:
            session_cookie_name = self.config.session_cookie_name or "session_id"
        else:
            session_cookie_name = "session_id"

        self.session_cookie_name = session_cookie_name
        manager = self.get_manager()
        session: type[BaseSessionInterface] = manager(
            session_key=request.cookies.get(session_cookie_name)  # type: ignore
        )
        await session.load()  # type: ignore
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
                samesite=request.session.get_cookie_samesite() or "lax",  # type: ignore
                expires=request.session.get_expiration_time(),
            )
