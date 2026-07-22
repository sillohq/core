"""sillo.services.admin.router — Admin URL routing and view dispatch."""

from __future__ import annotations

from sillo.routing import Route

from .views import (
    bulk_view,
    create_view,
    dashboard_view,
    delete_view,
    detail_view,
    list_view,
    login_view,
    logout_view,
    update_view,
)


def build_routes(site) -> list:
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
    async def handler(request, response):
        return await login_view(request, response, site)

    return handler


def _logout_handler(site):
    async def handler(request, response):
        return await logout_view(request, response, site)

    return handler


def _dashboard_handler(site):
    async def handler(request, response):
        return await dashboard_view(request, response, site)

    return handler


def _list_handler(site, model_cls, admin_cls):
    async def handler(request, response):
        return await list_view(request, response, site, model_cls, admin_cls)

    return handler


def _create_handler(site, model_cls, admin_cls):
    async def handler(request, response):
        return await create_view(request, response, site, model_cls, admin_cls)

    return handler


def _detail_handler(site, model_cls, admin_cls):
    async def handler(request, response, id):
        return await detail_view(request, response, site, model_cls, admin_cls, id)

    return handler


def _update_handler(site, model_cls, admin_cls):
    async def handler(request, response, id):
        return await update_view(request, response, site, model_cls, admin_cls, id)

    return handler


def _delete_handler(site, model_cls, admin_cls):
    async def handler(request, response, id):
        return await delete_view(request, response, site, model_cls, admin_cls, id)

    return handler


def _bulk_handler(site, model_cls, admin_cls):
    async def handler(request, response):
        return await bulk_view(request, response, site, model_cls, admin_cls)

    return handler
