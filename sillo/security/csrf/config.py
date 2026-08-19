import difflib
import typing
from collections.abc import Iterable
from typing import Any

#: Every setting this config understands. Anything else is a mistake, and the
#: constructor says so rather than storing it where nothing will read it.
SETTINGS = (
    "enabled",
    "required_urls",
    "exempt_urls",
    "sensitive_cookies",
    "safe_methods",
    "cookie_name",
    "cookie_path",
    "cookie_domain",
    "cookie_secure",
    "cookie_httponly",
    "cookie_samesite",
    "header_name",
    "form_field",
    "secret_key",
)


def reject_unknown_settings(names: Iterable[str], *, called: str) -> None:
    """Raise on any name that is not a CSRF setting.

    These used to be swept into the config dictionary with ``config.update``,
    so a name nothing reads was accepted in silence — ``secure=True`` left the
    real ``cookie_secure`` at ``False`` and the CSRF cookie went out over
    plain HTTP, with nothing to say so.

    Raises:
        TypeError: If any name is not a CSRF setting. The message suggests the
            closest real name, since the mistakes worth catching are near
            misses like ``secure`` for ``cookie_secure``.
    """
    unknown = [name for name in names if name not in SETTINGS]
    if not unknown:
        return

    lines = []
    for name in unknown:
        close = difflib.get_close_matches(name, SETTINGS, n=1, cutoff=0.5)
        if not close:
            close = [s for s in SETTINGS if s.endswith(name) or name.endswith(s)][:1]
        lines.append(
            f"  {name!r}" + (f" — did you mean {close[0]!r}?" if close else "")
        )

    raise TypeError(
        f"{called} got {'a setting' if len(unknown) == 1 else 'settings'} it does "
        f"not understand:\n\n"
        + "\n".join(lines)
        + "\n\nThe settings are:\n"
        + "\n".join(f"  {name}" for name in SETTINGS)
        + "\n"
    )


class CSRFConfig:
    """
    Typed configuration for CSRF middleware.
    """

    def __init__(
        self,
        enabled: bool = False,
        required_urls: list[str] | None = None,
        exempt_urls: list[str] | None = None,
        sensitive_cookies: list[str] | None = None,
        safe_methods: list[str] | None = None,
        cookie_name: str = "csrftoken",
        cookie_path: str = "/",
        cookie_domain: str | None = None,
        cookie_secure: bool = False,
        cookie_httponly: bool = False,
        cookie_samesite: typing.Literal["lax", "none", "strict"] = "lax",
        header_name: str = "X-CSRFToken",
        form_field: str = "csrftoken",
        secret_key: str | None = None,
        **kwargs: Any,
    ):
        """Build a CSRF configuration.

        Args:
            enabled: Whether the middleware enforces anything at all.
            required_urls: Path patterns that must carry a token. Defaults to
                ``["*"]`` — everything — so protection is not off by omission.
            exempt_urls: Path patterns excused from carrying one. These win
                over ``required_urls``.
            sensitive_cookies: Cookies that carry ambient authority. When set,
                only requests presenting one of them are checked, which is what
                lets a header-authenticated API skip the token. Naming none
                treats every request as sensitive.
            safe_methods: Methods never checked. Defaults to the read-only
                ones.
            cookie_name: Name of the cookie the token is sent in.
            cookie_path: Path the cookie is scoped to.
            cookie_domain: Domain the cookie is scoped to.
            cookie_secure: Whether the cookie is marked ``Secure``. Turn this
                on in production; it is off by default only so that local
                development over ``http://`` works.
            cookie_httponly: Whether the cookie is marked ``HttpOnly``.
                Defaults to ``False``, and wants to stay there: the double-
                submit pattern needs the page to read this cookie and echo it
                back in a header, which ``HttpOnly`` makes impossible. The
                token is not a credential — it is only useful to someone who
                can already read the page.
            cookie_samesite: ``"lax"``, ``"strict"`` or ``"none"``.
            header_name: Header the token may be echoed back in.
            form_field: Form field the token may be echoed back in, for
                ordinary HTML forms that cannot set a header.
            secret_key: The key tokens are signed with. Required whenever
                ``enabled`` is true.
            **kwargs: Accepted only so that a misspelling can be reported as
                such. Any name here that is not a CSRF setting raises.

        Raises:
            TypeError: If given a name that is not a CSRF setting.
        """
        reject_unknown_settings(kwargs, called="CSRFConfig()")

        self._config: dict[str, Any] = {
            "enabled": enabled,
            "required_urls": required_urls or ["*"],
            "exempt_urls": exempt_urls or [],
            "sensitive_cookies": sensitive_cookies or [],
            "safe_methods": safe_methods or ["GET", "HEAD", "OPTIONS", "TRACE"],
            "cookie_name": cookie_name,
            "cookie_path": cookie_path,
            "cookie_domain": cookie_domain,
            "cookie_secure": cookie_secure,
            "cookie_httponly": cookie_httponly,
            "cookie_samesite": cookie_samesite,
            "header_name": header_name,
            "form_field": form_field,
            "secret_key": secret_key,
        }

    def __getattr__(self, name: str):
        """Look up a setting not covered by an explicit property.

        Raises ``AttributeError`` for anything that is not a setting. Returning
        ``None`` instead, as this used to, made every misspelled read look like
        a setting that happened to be unset.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self.__dict__["_config"][name]
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__!r} has no setting {name!r}. "
                f"The settings are: {', '.join(SETTINGS)}."
            ) from None

    def to_dict(self) -> dict[str, Any]:
        return dict(self._config)

    @property
    def enabled(self) -> bool:
        """Enabled"""
        return self._config["enabled"]

    @property
    def required_urls(self) -> list[str]:
        """Required Urls"""
        return self._config["required_urls"]

    @property
    def exempt_urls(self) -> list[str]:
        """Exempt Urls"""
        return self._config["exempt_urls"]

    @property
    def sensitive_cookies(self) -> list[str]:
        """Sensitive Cookies"""
        return self._config["sensitive_cookies"]

    @property
    def safe_methods(self) -> list[str]:
        """Safe Methods"""
        return self._config["safe_methods"]

    @property
    def cookie_name(self) -> str:
        """Cookie Name"""
        return self._config["cookie_name"]

    @property
    def cookie_path(self) -> str:
        """Cookie Path"""
        return self._config["cookie_path"]

    @property
    def cookie_domain(self) -> str | None:
        """Cookie Domain"""
        return self._config["cookie_domain"]

    @property
    def cookie_secure(self) -> bool:
        """Cookie Secure"""
        return self._config["cookie_secure"]

    @property
    def cookie_httponly(self) -> bool:
        """Cookie Httponly"""
        return self._config["cookie_httponly"]

    @property
    def cookie_samesite(self) -> typing.Literal["lax", "none", "strict"]:
        """Cookie Samesite"""
        return self._config["cookie_samesite"]

    @property
    def header_name(self) -> str:
        """Header Name"""
        return self._config["header_name"]

    @property
    def form_field(self) -> str:
        """Form field the token may be echoed back in."""
        return self._config["form_field"]

    @property
    def secret_key(self) -> str | None:
        """Secret Key"""
        return self._config.get("secret_key")
