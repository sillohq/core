import difflib
from collections.abc import Iterable
from typing import Any, Literal

#: Every setting this config understands. Anything else is a mistake, and the
#: constructor says so rather than storing it where nothing will read it.
SETTINGS = (
    "session_cookie_name",
    "session_expiration_time",
    "session_permanent",
    "session_refresh_each_request",
    "session_cookie_secure",
    "session_cookie_httponly",
    "session_cookie_samesite",
    "session_cookie_path",
    "session_cookie_domain",
    "session_file_storage_path",
    "manager",
)


def reject_unknown_settings(names: Iterable[str], *, called: str) -> None:
    """Raise on any name that is not a session setting.

    Session settings used to be collected with ``**kwargs`` and merged into the
    config dictionary unchecked, so a name that nothing reads was accepted in
    silence. That is a bad trade for a cookie: passing ``cookie_secure=False``
    left the real ``session_cookie_secure`` at its default of ``True``, the
    cookie went out marked ``Secure``, and browsers stopped returning it over
    plain HTTP — so sessions quietly did nothing in local development, with
    no error to point at.

    Args:
        names: The keyword names the caller supplied.
        called: What to name in the error, for instance ``"SessionConfig()"``.

    Raises:
        TypeError: If any name is not a session setting. The message suggests
            the closest real name, since the mistakes worth catching are near
            misses like ``cookie_secure`` for ``session_cookie_secure``.
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


class SessionConfig:
    """
    Typed configuration for Session middleware.
    All session settings should be passed here - only secret_key comes from app-level config.
    """

    def __init__(
        self,
        session_cookie_name: str = "session_id",
        session_expiration_time: int = 86400,
        session_permanent: bool = True,
        session_refresh_each_request: bool = True,
        session_cookie_secure: bool = True,
        session_cookie_httponly: bool = True,
        session_cookie_samesite: str = "lax",
        session_cookie_path: str = "/",
        session_cookie_domain: str | None = None,
        session_file_storage_path: str | None = None,
        manager: Any | None = None,
        **kwargs: Any,
    ):
        """Build a session configuration.

        Args:
            session_cookie_name: Name of the cookie the session id is stored in.
            session_expiration_time: Session lifetime in seconds.
            session_permanent: Whether the cookie carries an expiry at all. When
                ``False`` the browser drops it at the end of the session.
            session_refresh_each_request: Whether to re-send the cookie on every
                response, sliding the expiry forward.
            session_cookie_secure: Whether the cookie is marked ``Secure``.
                Leave it on in production; browsers will not return a ``Secure``
                cookie over plain HTTP, so local development over ``http://``
                needs this set to ``False``.
            session_cookie_httponly: Whether the cookie is marked ``HttpOnly``,
                keeping it out of reach of JavaScript.
            session_cookie_samesite: ``"lax"``, ``"strict"`` or ``"none"``.
            session_cookie_path: Path the cookie is scoped to.
            session_cookie_domain: Domain the cookie is scoped to, or ``None``
                for the host that set it.
            session_file_storage_path: Directory the file backend writes to.
            manager: A session interface to use instead of the default.
            **kwargs: Accepted only so that a misspelling can be reported as
                such. Any name here that is not a session setting raises.

        Raises:
            TypeError: If given a name that is not a session setting.
        """
        reject_unknown_settings(kwargs, called="SessionConfig()")

        self._config: dict[str, Any] = {
            "session_cookie_name": session_cookie_name,
            "session_expiration_time": session_expiration_time,
            "session_permanent": session_permanent,
            "session_refresh_each_request": session_refresh_each_request,
            "session_cookie_secure": session_cookie_secure,
            "session_cookie_httponly": session_cookie_httponly,
            "session_cookie_samesite": session_cookie_samesite,
            "session_cookie_path": session_cookie_path,
            "session_cookie_domain": session_cookie_domain,
            "session_file_storage_path": session_file_storage_path,
            "manager": manager,
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
    def session_cookie_name(self) -> str:
        """Name of the cookie the session id is stored in."""
        return str(self._config.get("session_cookie_name", "session_id"))

    @property
    def session_expiration_time(self) -> int:
        """Session lifetime in seconds."""
        return int(self._config.get("session_expiration_time", 86400))  # ty: ignore[invalid-argument-type]

    @property
    def session_permanent(self) -> bool:
        """Whether the cookie carries an expiry at all."""
        return bool(self._config.get("session_permanent", True))

    @property
    def session_refresh_each_request(self) -> bool:
        """Whether every response re-sends the cookie, sliding the expiry."""
        return bool(self._config.get("session_refresh_each_request", True))

    @property
    def session_cookie_secure(self) -> bool:
        """Whether the cookie is marked ``Secure``. Turn this off to develop over plain HTTP."""
        return bool(self._config.get("session_cookie_secure", True))

    @property
    def session_cookie_httponly(self) -> bool:
        """Whether the cookie is marked ``HttpOnly``."""
        return bool(self._config.get("session_cookie_httponly", True))

    @property
    def session_cookie_samesite(self) -> Literal["lax", "strict", "none"]:
        """The cookie's SameSite attribute."""
        return str(self._config.get("session_cookie_samesite", "lax"))  # ty: ignore[invalid-return-type]

    @property
    def session_cookie_path(self) -> str:
        """Path the cookie is scoped to."""
        return str(self._config.get("session_cookie_path", "/"))

    @property
    def session_cookie_domain(self) -> str | None:
        """Domain the cookie is scoped to, or ``None`` for the setting host."""
        return self._config.get("session_cookie_domain")  # ty: ignore[invalid-return-type]

    @property
    def session_file_storage_path(self) -> str | None:
        """Directory the file backend writes to."""
        return self._config.get("session_file_storage_path")  # ty: ignore[invalid-return-type]

    @property
    def manager(self) -> Any | None:
        """A session backend instance, or ``None`` for the signed-cookie default."""
        return self._config.get("manager")
