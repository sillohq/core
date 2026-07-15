from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sillo.helpers import jwt as _jwt


class TokenForUser:
    """Create and manage JWT tokens bound to a user."""

    def __init__(
        self,
        user,
        secret: str,
        algorithm: str = "HS256",
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
    ):
        self.user = user
        self.secret = secret
        self.algorithm = algorithm
        self.issuer = issuer
        self.audience = audience

    def _base_payload(self) -> dict:
        now = datetime.now(timezone.utc)
        payload: dict = {"sub": str(self.user.identity), "iat": now, "typ": "access"}
        if self.issuer:
            payload["iss"] = self.issuer
        if self.audience:
            payload["aud"] = self.audience
        return payload

    def access_token(self, expires_in: Optional[timedelta] = None) -> str:
        payload = self._base_payload()
        payload["typ"] = "access"
        payload["exp"] = (
            datetime.now(timezone.utc) + expires_in
            if expires_in
            else datetime.now(timezone.utc) + timedelta(minutes=15)
        )
        return _jwt.encode(payload, self.secret, self.algorithm)

    def refresh_token(self, expires_in: Optional[timedelta] = None) -> str:
        payload = self._base_payload()
        payload["typ"] = "refresh"
        payload["exp"] = (
            datetime.now(timezone.utc) + expires_in
            if expires_in
            else datetime.now(timezone.utc) + timedelta(days=7)
        )
        return _jwt.encode(payload, self.secret, self.algorithm)

    def token_pair(
        self,
        access_expires: Optional[timedelta] = None,
        refresh_expires: Optional[timedelta] = None,
    ) -> dict:
        return {
            "access_token": self.access_token(access_expires),
            "refresh_token": self.refresh_token(refresh_expires),
            "token_type": "bearer",
        }

    def verify(self, token: str) -> dict:
        return _jwt.decode(
            token,
            self.secret,
            algorithms=[self.algorithm],
            audience=self.audience,
            issuer=self.issuer,
        )

    def verify_no_expire(self, token: str) -> dict:
        return _jwt.decode(
            token,
            self.secret,
            algorithms=[self.algorithm],
            audience=self.audience,
            issuer=self.issuer,
            options={"verify_exp": False},
        )

    @staticmethod
    def decode_unverified(token: str) -> dict:
        return _jwt.decode_without_verification(token)

    @staticmethod
    def get_unverified_header(token: str) -> dict:
        return _jwt.get_unverified_header(token)
