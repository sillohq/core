from __future__ import annotations

from typing import Any

from sillo.auth.backends.base import AuthenticationBackend
from sillo.auth.model import AuthResult
from sillo.http import Request

DEFAULT_SESSION_KEY = "user"
DEFAULT_IDENTIFIER = "id"


def login(request: Request, user, session_key: str = DEFAULT_SESSION_KEY, identifier: str = DEFAULT_IDENTIFIER):
    assert "session" in request.scope, "No Session Middleware Installed"
    if request.session.get(session_key):
        del request.session[session_key]
    request.session[session_key] = {
        identifier: user.identity,
        "display_name": user.display_name,
    }


def logout(request: Request, session_key: str = DEFAULT_SESSION_KEY):
    assert "session" in request.scope, "No Session Middleware Installed"
    del request.session[session_key]


class SessionAuthBackend(AuthenticationBackend):
    def __init__(self, session_key: str = DEFAULT_SESSION_KEY, identifier: str = DEFAULT_IDENTIFIER):
        self.session_key = session_key
        self.identifier = identifier

    async def authenticate(self, request: Request) -> Any:
        assert "session" in request.scope, "No Session Middleware Installed"
        user = request.session.get(self.session_key)

        if not user:
            return AuthResult(success=False, identity="", scope="")

        return AuthResult(
            success=True, identity=user.get(self.identifier, ""), scope="session"
        )
