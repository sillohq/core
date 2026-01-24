from typing import Any, Optional

from nexios.config.base import MakeConfig


class SessionConfig(MakeConfig):
    """
    Typed configuration for Session middleware.
    """

    def __init__(
        self,
        session_cookie_name: str = "session_id",
        manager: Optional[Any] = None,
        **kwargs: Any,
    ):
        config = {
            "session_cookie_name": session_cookie_name,
            "manager": manager,
        }
        super().__init__(config=config, **kwargs)

    @property
    def session_cookie_name(self) -> str:
        return self._config["session_cookie_name"]

    @property
    def manager(self) -> Optional[Any]:
        return self._config["manager"]
