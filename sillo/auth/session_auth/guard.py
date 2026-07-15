from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sillo.auth.session_auth.backend import (
    login as _session_login,
    logout as _session_logout,
)
from sillo.http import Request


class SessionGuard:
    def __init__(self, backend=None, user_model=None):
        self.backend = backend
        self.user_model = user_model

    async def attempt(self, request: Request, **credentials) -> bool:
        email = credentials.get("email")
        password = credentials.get("password")
        if not email or not password or self.user_model is None:
            return False
        user = (
            await self.user_model.objects.get_by_email(email)
            if hasattr(self.user_model, "objects")
            else None
        )
        if user is None or not user.check_password(password):
            return False
        await self.login(request, user)
        return True

    async def login(self, request: Request, user) -> None:
        _session_login(request, user)
        if hasattr(user, "set_last_login"):
            await user.set_last_login()

    async def logout(self, request: Request) -> None:
        _session_logout(request)

    async def user(self, request: Request):
        session_user = (
            request.session.get("user") if hasattr(request, "session") else None
        )
        if session_user and self.user_model:
            uid = session_user.get("id")
            if uid:
                return (
                    await self.user_model.objects.get_by_id(int(uid))
                    if hasattr(self.user_model, "objects")
                    else None
                )
        return None

    async def check(self, request: Request) -> bool:
        if not hasattr(request, "session"):
            return False
        return bool(request.session.get("user"))

    async def id(self, request: Request) -> Optional[str]:
        session_user = (
            request.session.get("user") if hasattr(request, "session") else None
        )
        return str(session_user.get("id")) if session_user else None

    async def validate(self, request: Request, credentials: dict) -> bool:
        email = credentials.get("email")
        password = credentials.get("password")
        if not email or not password or self.user_model is None:
            return False
        user = (
            await self.user_model.objects.get_by_email(email)
            if hasattr(self.user_model, "objects")
            else None
        )
        if user is None or not user.check_password(password):
            return False
        request.scope["_validated_user"] = user
        return True
