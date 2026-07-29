"""Configuration for password hashing schemes."""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SchemeConfig:
    """Configuration for a hashing scheme."""

    name: str
    package: Optional[str] = None
    default: bool = False
    deprecated: bool = False


# Supported hashing schemes
SCHEMES: Dict[str, SchemeConfig] = {
    "bcrypt": SchemeConfig(
        name="bcrypt",
        package="bcrypt",
        default=True,
    ),
    "argon2": SchemeConfig(
        name="argon2",
        package="argon2-cffi",
    ),
    "scrypt": SchemeConfig(
        name="scrypt",
        package="scrypt",
    ),
    "pbkdf2_sha256": SchemeConfig(
        name="pbkdf2_sha256",
        package=None,  # Built-in
    ),
    "pbkdf2_sha512": SchemeConfig(
        name="pbkdf2_sha512",
        package=None,  # Built-in
    ),
}


def get_default_scheme() -> str:
    """Get the default hashing scheme."""
    for name, config in SCHEMES.items():
        if config.default:
            return name
    return "bcrypt"


def is_scheme_available(scheme: str) -> bool:
    """Check if a scheme is available (its package is installed)."""
    config = SCHEMES.get(scheme)
    if not config:
        return False

    if config.package is None:
        return True

    try:
        __import__(config.package.replace("-", "_"))
        return True
    except ImportError:
        return False


def get_available_schemes() -> list[str]:
    """Get list of available schemes."""
    return [name for name in SCHEMES.keys() if is_scheme_available(name)]
