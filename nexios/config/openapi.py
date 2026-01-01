from typing import Any, List, Optional
from nexios.config.base import MakeConfig

class OpenAPIConfig(MakeConfig):
    """
    Typed configuration for OpenAPI documentation.
    """
    def __init__(
        self,
        title: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        swagger_url: str = "/docs",
        redoc_url: str = "/redoc",
        openapi_url: str = "/openapi.json",
        license: Optional[Any] = None,
        contact: Optional[Any] = None,
        servers: Optional[List[Any]] = None,
        termsOfService: Optional[str] = None,
        **kwargs: Any
    ):
        config = {
            "title": title,
            "version": version,
            "description": description,
            "swagger_url": swagger_url,
            "redoc_url": redoc_url,
            "openapi_url": openapi_url,
            "license": license,
            "contact": contact,
            "servers": servers,
            "termsOfService": termsOfService,
        }
        super().__init__(config=config, **kwargs)

    @property
    def title(self) -> Optional[str]:
        return self._config["title"]

    @property
    def version(self) -> Optional[str]:
        return self._config["version"]

    @property
    def description(self) -> Optional[str]:
        return self._config["description"]

    @property
    def swagger_url(self) -> str:
        return self._config["swagger_url"]

    @property
    def redoc_url(self) -> str:
        return self._config["redoc_url"]

    @property
    def openapi_url(self) -> str:
        return self._config["openapi_url"]

    @property
    def license(self) -> Optional[Any]:
        return self._config["license"]

    @property
    def contact(self) -> Optional[Any]:
        return self._config["contact"]

    @property
    def servers(self) -> Optional[List[Any]]:
        return self._config["servers"]

    @property
    def termsOfService(self) -> Optional[str]:
        return self._config["termsOfService"]
