from dataclasses import dataclass


@dataclass
class AuthResult:
    identity: str
    scope: str
    success: bool
