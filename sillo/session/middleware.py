from sillo.session.session_objects import Session
import typing
from typing import Any, Optional

from sillo.http import Request, Response
from sillo.middleware.base import BaseMiddleware

from .base import BaseSessionInterface
from .config import SessionConfig
from .signed_cookies import SignedSessionManager


class SessionMiddleware(BaseMiddleware):
    def __init__(
        self,
        config: Optional[SessionConfig] = None,
        manager: Optional[BaseSessionInterface] = None,
        secret_key: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)

        self.session_config = config or SessionConfig()

        if manager is not None:
            self.session_interface = manager
        else:
            self.session_interface = SignedSessionManager(secret_key=secret_key)

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ):
        cookie_name = self.session_config.session_cookie_name or "session_id"
        session_key = request.cookies.get(cookie_name)

        session = self.session_interface.create_session(session_key)
        await session.load()

        request.scope["session"] = session

        return await call_next()

    async def process_response(self, request: Request, response: Response):
        session: Session | None = request.scope.get("session")
        if session is None:
            return

        cookie_name = self.session_config.session_cookie_name or "session_id"

        if session.is_empty() and session.accessed:
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
