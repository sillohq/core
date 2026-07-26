"""sillo.admin.router — Admin URL routing and view dispatch."""

from __future__ import annotations

from sillo.core.routing import Route

from .routes import (
    bulk_view,
    create_view,
    dashboard_view,
    delete_view,
    detail_view,
    export_view,
    list_view,
    login_view,
    logout_view,
    query_view,
    update_view,
)


def build_routes(site) -> list:
    """Build Routes

    Args:
        site: [description]

    Returns:
        [description]

    Raises:
        [description]
    """
    p = site.prefix
    routes = [
        Route(
            f"{p}/login/",
            _login_handler(site),
            methods=["GET", "POST"],
            name="admin-login",
        ),
        Route(
            f"{p}/logout/", _logout_handler(site), methods=["GET"], name="admin-logout"
        ),
        Route(
            f"{p}/",
            _dashboard_handler(site),
            methods=["GET"],
            name="admin-dashboard",
        ),
        Route(
            f"{p}/query/",
            _query_handler(site),
            methods=["GET", "POST"],
            name="admin-query",
        ),
    ]
    for model_cls, admin_cls in site.registry:
        name = model_cls.__name__.lower()
        b = f"{p}/{name}/"
        routes += [
            Route(
                b,
                _list_handler(site, model_cls, admin_cls),
                methods=["GET"],
                name=f"admin-{name}-list",
            ),
            Route(
                f"{b}create/",
                _create_handler(site, model_cls, admin_cls),
                methods=["GET", "POST"],
                name=f"admin-{name}-create",
            ),
            Route(
                f"{b}export/",
                _export_handler(site, model_cls, admin_cls),
                methods=["GET"],
                name=f"admin-{name}-export",
            ),
            Route(
                f"{b}{{id}}/",
                _detail_handler(site, model_cls, admin_cls),
                methods=["GET"],
                name=f"admin-{name}-detail",
            ),
            Route(
                f"{b}{{id}}/update/",
                _update_handler(site, model_cls, admin_cls),
                methods=["GET", "POST"],
                name=f"admin-{name}-update",
            ),
            Route(
                f"{b}{{id}}/delete/",
                _delete_handler(site, model_cls, admin_cls),
                methods=["GET", "POST"],
                name=f"admin-{name}-delete",
            ),
            Route(
                f"{b}bulk/",
                _bulk_handler(site, model_cls, admin_cls),
                methods=["POST"],
                name=f"admin-{name}-bulk",
            ),
        ]
    return routes


def _login_handler(site):
    """Login Handler

    Args:
        site: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response):
        """Handler

        Args:
            request: [description]
            response: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await login_view(request, response, site)

    return handler


def _logout_handler(site):
    """Logout Handler

    Args:
        site: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response):
        """Handler

        Args:
            request: [description]
            response: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await logout_view(request, response, site)

    return handler


def _dashboard_handler(site):
    """Dashboard Handler

    Args:
        site: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response):
        """Handler

        Args:
            request: [description]
            response: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await dashboard_view(request, response, site)

    return handler


def _query_handler(site):
    """Query Handler

    Args:
        site: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response):
        """Handler

        Args:
            request: [description]
            response: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await query_view(request, response, site)

    return handler


def _export_handler(site, model_cls, admin_cls):
    """Export Handler

    Args:
        site: [description]
        model_cls: [description]
        admin_cls: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response):
        """Handler

        Args:
            request: [description]
            response: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await export_view(request, response, site, model_cls, admin_cls)

    return handler


def _list_handler(site, model_cls, admin_cls):
    """List Handler

    Args:
        site: [description]
        model_cls: [description]
        admin_cls: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response):
        """Handler

        Args:
            request: [description]
            response: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await list_view(request, response, site, model_cls, admin_cls)

    return handler


def _create_handler(site, model_cls, admin_cls):
    """Create Handler

    Args:
        site: [description]
        model_cls: [description]
        admin_cls: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response):
        """Handler

        Args:
            request: [description]
            response: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await create_view(request, response, site, model_cls, admin_cls)

    return handler


def _detail_handler(site, model_cls, admin_cls):
    """Detail Handler

    Args:
        site: [description]
        model_cls: [description]
        admin_cls: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response, id):
        """Handler

        Args:
            request: [description]
            response: [description]
            id: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await detail_view(request, response, site, model_cls, admin_cls, id)

    return handler


def _update_handler(site, model_cls, admin_cls):
    """Update Handler

    Args:
        site: [description]
        model_cls: [description]
        admin_cls: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response, id):
        """Handler

        Args:
            request: [description]
            response: [description]
            id: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await update_view(request, response, site, model_cls, admin_cls, id)

    return handler


def _delete_handler(site, model_cls, admin_cls):
    """Delete Handler

    Args:
        site: [description]
        model_cls: [description]
        admin_cls: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response, id):
        """Handler

        Args:
            request: [description]
            response: [description]
            id: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await delete_view(request, response, site, model_cls, admin_cls, id)

    return handler


def _bulk_handler(site, model_cls, admin_cls):
    """Bulk Handler

    Args:
        site: [description]
        model_cls: [description]
        admin_cls: [description]

    Returns:
        [description]

    Raises:
        [description]
    """

    async def handler(request, response):
        """Handler

        Args:
            request: [description]
            response: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await bulk_view(request, response, site, model_cls, admin_cls)

    return handler
