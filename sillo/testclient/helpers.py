"""
Helper functions for creating sync and async test clients for sillo applications.
"""

from collections.abc import Sequence
from typing import Any

from sillo import SilloApp
from sillo.core.dependencies import Depend
from sillo.core.routing import Route
from sillo.core.routing.base import BaseRoute
from sillo.testclient import AsyncTestClient, TestClient
from sillo.types import ExceptionHandlerType


def create_client(
    title: str | None = None,
    version: str | None = None,
    description: str | None = None,
    server_error_handler: ExceptionHandlerType | None = None,
    lifespan: Any | None = None,
    routes: Sequence[BaseRoute] = [],
    dependencies: list[Depend] | None = None,
    client_config: dict[str, Any] | None = None,
) -> TestClient:
    """Create a synchronous ``TestClient`` for a sillo application.

    Builds a minimal ``SilloApp`` with the supplied parameters, then wraps
    it in a ``TestClient`` that speaks ASGI directly (no network socket).
    An optional ``client_config`` dict overrides the default client
    settings (base URL, redirect behaviour, ASGI backend, etc.).

    Args:
        title: Application title forwarded to ``SilloApp``.
        version: Application version.
        description: Application description.
        server_error_handler: Custom 500 error handler.
        lifespan: Lifespan context manager.
        routes: Initial route list.
        dependencies: Global dependency list.
        client_config: Overrides for ``TestClient`` constructor kwargs.

    Returns:
        A configured synchronous ``TestClient`` instance.
    """
    app = SilloApp(
        title=title,
        version=version,
        description=description,
        server_error_handler=server_error_handler,
        lifespan=lifespan,
        routes=routes,
        dependencies=dependencies,
    )

    default_client_config = {
        "base_url": "http://testserver",
        "raise_server_exceptions": True,
        "root_path": "",
        "backend": "asyncio",
        "backend_options": None,
        "cookies": None,
        "headers": None,
        "follow_redirects": True,
        "check_asgi_conformance": True,
    }

    if client_config:
        default_client_config.update(client_config)

    return TestClient(
        app=app,
        base_url=default_client_config["base_url"],
        raise_server_exceptions=default_client_config["raise_server_exceptions"],
        root_path=default_client_config["root_path"],
        backend=default_client_config["backend"],
        backend_options=default_client_config["backend_options"],
        cookies=default_client_config["cookies"],
        headers=default_client_config["headers"],
        follow_redirects=default_client_config["follow_redirects"],
        check_asgi_conformance=default_client_config["check_asgi_conformance"],
    )


def create_async_client(
    title: str | None = None,
    version: str | None = None,
    description: str | None = None,
    server_error_handler: ExceptionHandlerType | None = None,
    lifespan: Any | None = None,
    routes: Sequence[Route] = [],
    dependencies: list[Depend] | None = None,
    client_config: dict[str, Any] | None = None,
) -> AsyncTestClient:
    """Create an asynchronous ``AsyncTestClient`` for a sillo application.

    Identical in purpose to ``create_client`` but returns the async
    variant so tests can ``await`` ASGI calls directly.

    Args:
        title: Application title forwarded to ``SilloApp``.
        version: Application version.
        description: Application description.
        server_error_handler: Custom 500 error handler.
        lifespan: Lifespan context manager.
        routes: Initial route list.
        dependencies: Global dependency list.
        client_config: Overrides for ``AsyncTestClient`` constructor kwargs.

    Returns:
        A configured ``AsyncTestClient`` instance.
    """
    app = SilloApp(
        title=title,
        version=version,
        description=description,
        server_error_handler=server_error_handler,
        lifespan=lifespan,
        routes=routes,
        dependencies=dependencies,
    )

    default_client_config = {
        "base_url": "http://testserver",
        "raise_server_exceptions": True,
        "root_path": "",
        "backend": "asyncio",
        "backend_options": None,
        "cookies": None,
        "headers": None,
        "follow_redirects": True,
        "check_asgi_conformance": True,
    }

    if client_config:
        default_client_config.update(client_config)

    return AsyncTestClient(
        app=app,
        base_url=default_client_config["base_url"],
        raise_server_exceptions=default_client_config["raise_server_exceptions"],
        root_path=default_client_config["root_path"],
        backend=default_client_config["backend"],
        backend_options=default_client_config["backend_options"],
        cookies=default_client_config["cookies"],
        headers=default_client_config["headers"],
        follow_redirects=default_client_config["follow_redirects"],
        check_asgi_conformance=default_client_config["check_asgi_conformance"],
    )
