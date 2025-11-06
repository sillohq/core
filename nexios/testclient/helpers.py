"""
Helper functions for creating sync and async test clients for Nexios applications.
"""

from typing import Any, Dict, List, Optional

from nexios import MakeConfig, NexiosApp
from nexios.dependencies import Depend
from nexios.routing import Route
from nexios.testclient import AsyncTestClient, TestClient
from nexios.types import ExceptionHandlerType


def create_client(
    config: Optional[MakeConfig] = None,
    title: Optional[str] = None,
    version: Optional[str] = None,
    description: Optional[str] = None,
    server_error_handler: Optional[ExceptionHandlerType] = None,
    lifespan: Optional[Any] = None,
    routes: Optional[List[Route]] = None,
    dependencies: Optional[List[Depend]] = None,
    client_config: Optional[Dict[str, Any]] = None,
) -> TestClient:
    """
    Create a synchronous test client for a Nexios application.
    """
    app = NexiosApp(
        config=config,
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
    config: Optional[MakeConfig] = None,
    title: Optional[str] = None,
    version: Optional[str] = None,
    description: Optional[str] = None,
    server_error_handler: Optional[ExceptionHandlerType] = None,
    lifespan: Optional[Any] = None,
    routes: Optional[List[Route]] = None,
    dependencies: Optional[List[Depend]] = None,
    client_config: Optional[Dict[str, Any]] = None,
) -> AsyncTestClient:
    """
    Create an asynchronous test client for a Nexios application.
    """
    app = NexiosApp(
        config=config,
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
