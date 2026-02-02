import typing

from nexios.config import get_config
from nexios.http import Request, Response
from nexios.middleware.base import BaseMiddleware

from .base import BaseSessionInterface
from .signed_cookies import SignedSessionManager


class SessionMiddleware(BaseMiddleware):
    def get_manager(self):
        if not self.config:
            return SignedSessionManager
        else:
            return self.config.manager or SignedSessionManager

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ):
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
        await call_next()

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
