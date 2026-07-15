from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sillo.auth.jwt_auth.models import JWTToken, TokenBlacklist
from sillo.auth.jwt_auth.tokens import TokenForUser


class JWTUserMixin:
    async def issue_token_pair(
        self,
        secret: str,
        access_expires: Optional[timedelta] = None,
        refresh_expires: Optional[timedelta] = None,
        algorithm: str = "HS256",
    ) -> dict:
        tokens = TokenForUser(self, secret=secret, algorithm=algorithm)
        family = secrets.token_hex(32)
        access_jti = secrets.token_hex(16)
        access = tokens.access_token(access_expires or timedelta(minutes=15))
        refresh_jti = secrets.token_hex(16)
        refresh = tokens.refresh_token(refresh_expires or timedelta(days=7))
        now = datetime.now(timezone.utc)
        await JWTToken.create(
            user_id=int(str(self.identity)),
            token_jti=access_jti,
            token_family=family,
            token_type="access",
            expires_at=now + (access_expires or timedelta(minutes=15)),
        )
        await JWTToken.create(
            user_id=int(str(self.identity)),
            token_jti=refresh_jti,
            token_family=family,
            token_type="refresh",
            expires_at=now + (refresh_expires or timedelta(days=7)),
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "token_family": family,
        }

    async def refresh_token_pair(
        self,
        refresh_token: str,
        secret: str,
        algorithm: str = "HS256",
    ) -> dict:
        tokens = TokenForUser(self, secret=secret, algorithm=algorithm)
        try:
            payload = tokens.verify_no_expire(refresh_token)
        except Exception:
            raise ValueError("Invalid refresh token")
        jti = payload.get("jti", refresh_token)
        existing = await JWTToken.filter(token_jti=jti).first()
        if existing is None or existing.token_type != "refresh":
            raise ValueError("Unknown refresh token")
        if existing.revoked:
            await JWTToken.revoke_family(existing.token_family)
            raise ValueError("Token family has been revoked — possible token theft")
        if existing.consumed_at is not None:
            await JWTToken.revoke_family(existing.token_family)
            raise ValueError("Refresh token already consumed — possible token theft")
        await existing.consume()
        family = existing.token_family
        access_expires = timedelta(minutes=15)
        refresh_expires = timedelta(days=7)
        access_jti = secrets.token_hex(16)
        access = tokens.access_token(access_expires)
        refresh_jti = secrets.token_hex(16)
        refresh = tokens.refresh_token(refresh_expires)
        now = datetime.now(timezone.utc)
        await JWTToken.create(
            user_id=int(str(self.identity)),
            token_jti=access_jti,
            token_family=family,
            token_type="access",
            expires_at=now + access_expires,
        )
        await JWTToken.create(
            user_id=int(str(self.identity)),
            token_jti=refresh_jti,
            token_family=family,
            token_type="refresh",
            expires_at=now + refresh_expires,
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "token_family": family,
        }

    async def revoke_all_tokens(self) -> int:
        return await JWTToken.revoke_all_for_user(int(str(self.identity)))

    async def blacklist_token(self, token: str, secret: str) -> bool:
        try:
            payload = TokenForUser(self, secret=secret).verify_no_expire(token)
        except Exception:
            return False
        jti = payload.get("jti", token)
        exp = payload.get("exp")
        if exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        await TokenBlacklist.get_or_create(
            token_jti=jti,
            defaults={"expires_at": expires_at},
        )
        return True

    async def active_token_count(self) -> int:
        return await JWTToken.filter(
            user_id=int(str(self.identity)),
            revoked=False,
            expires_at__gt=datetime.now(timezone.utc),
        ).count()
