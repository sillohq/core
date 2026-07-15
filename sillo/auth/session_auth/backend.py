from __future__ import annotations

from typing import Any

from sillo.auth.backends.base import AuthenticationBackend
from sillo.auth.model import AuthResult
from sillo.http import Request

_session_key = "user"
_identifier = "id"


def login(request: Request, user):
    assert "session" in request.scope, "No Session Middleware Installed"
    if request.session.get(_session_key):
        del request.session[_session_key]
    request.session[_session_key] = {
        _identifier: user.identity,
        "display_name": user.display_name,
    }


def logout(request: Request):
    assert "session" in request.scope, "No Session Middleware Installed"
    del request.session[_session_key]


class SessionAuthBackend(AuthenticationBackend):
    def __init__(self, session_key: str = "user", identifier: str = "id"):
        global _session_key, _identifier
        _session_key = session_key
        self.key = session_key
        _identifier = identifier

    async def authenticate(self, request: Request) -> Any:
        assert "session" in request.scope, "No Session Middleware Installed"
        user = request.session.get(_session_key)

        if not user:
            return AuthResult(success=False, identity="", scope="")

        return AuthResult(
            success=True, identity=user.get(_identifier, ""), scope="session"
        )
