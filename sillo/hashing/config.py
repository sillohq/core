"""Configuration for password hashing schemes."""

from dataclasses import dataclass


@dataclass
class SchemeConfig:
    """Configuration for a hashing scheme."""

    name: str
    package: str | None = None
    #: The importable module, when it differs from the distribution name.
    #: ``argon2-cffi`` installs a module called ``argon2``, so deriving one
    #: from the other by swapping dashes for underscores looks for
    #: ``argon2_cffi`` and never finds it -- which reported argon2 as missing
    #: on machines that had it. The two names are unrelated strings and are
    #: kept as unrelated strings.
    module: str | None = None
    default: bool = False
    deprecated: bool = False

    @property
    def import_name(self) -> str | None:
        """The name to import to decide whether the scheme is usable."""
        return self.module or self.package


# Supported hashing schemes
SCHEMES: dict[str, SchemeConfig] = {
    "bcrypt": SchemeConfig(
        name="bcrypt",
        package="bcrypt",
        default=True,
    ),
    "argon2": SchemeConfig(
        name="argon2",
        package="argon2-cffi",
        module="argon2",
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
    """Get the default hashing scheme.

    Attempts to use the preferred default (bcrypt), but falls back to
    pbkdf2_sha256 (built-in) if bcrypt is not installed.
    """
    for name, config in SCHEMES.items():
        if config.default and is_scheme_available(name):
            return name
    # Fall back to built-in pbkdf2_sha256 if bcrypt not available
    return "pbkdf2_sha256"


def is_scheme_available(scheme: str) -> bool:
    """Check if a scheme is available (its package is installed)."""
    config = SCHEMES.get(scheme)
    if not config:
        return False

    module = config.import_name
    if module is None:
        return True

    try:
        __import__(module)
        return True
    except ImportError:
        return False


def install_hint(scheme: str) -> str:
    """How to actually get `scheme`, for the message shown when it is missing.

    The distribution name, not the scheme name: ``pip install argon2`` names a
    different, unrelated project, so the old message sent people to the wrong
    package to fix a problem they did not have.
    """
    config = SCHEMES.get(scheme)
    if config is None or config.package is None:
        return f"'{scheme}' is not a known scheme"
    return f"pip install {config.package}"


def get_available_schemes() -> list[str]:
    """Get list of available schemes."""
    return [name for name in SCHEMES if is_scheme_available(name)]
