from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sillo.auth.session_auth.models import Session


class SessionUserMixin:
    async def create_session(
        self, session_key: str, ip_address: Optional[str] = None,
        user_agent: Optional[str] = None, device_name: Optional[str] = None,
        duration_seconds: int = 86400,
    ):
        return await Session.create(
            user_id=int(str(self.identity)), session_key=session_key,
            ip_address=ip_address, user_agent=user_agent, device_name=device_name,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=duration_seconds),
        )

    async def get_active_sessions(self):
        now = datetime.now(timezone.utc)
        return await Session.filter(
            user_id=int(str(self.identity)), is_active=True,
            expires_at__gt=now,
        ).all()

    async def logout_everywhere(self) -> int:
        return await Session.terminate_all_for_user(int(str(self.identity)))

    async def logout_session(self, session_key: str) -> bool:
        session = await Session.filter(
            user_id=int(str(self.identity)), session_key=session_key,
            is_active=True,
        ).first()
        if session:
            await session.terminate()
            return True
        return False

    async def active_session_count(self) -> int:
        now = datetime.now(timezone.utc)
        return await Session.filter(
            user_id=int(str(self.identity)), is_active=True,
            expires_at__gt=now,
        ).count()
