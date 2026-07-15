"""sillo.services.admin.router — Admin URL routing and view dispatch."""

from __future__ import annotations

from sillo.routing import Route


class AdminRouter:
    def __init__(self, site):
        self.site = site

    def build_routes(self) -> list:
        from .views import (
            DashboardView, ListView, DetailView,
            CreateView, UpdateView, DeleteView, LoginView,
        )
        p = self.site.prefix
        routes = [
            Route(f"{p}/login/", self._login(LoginView), methods=["GET", "POST"], name="admin-login"),
            Route(f"{p}/logout/", self._logout, methods=["GET"], name="admin-logout"),
            Route(f"{p}/", self._dash(DashboardView), methods=["GET"], name="admin-dashboard"),
        ]
        for model_cls, admin_cls in self.site.registry:
            name = model_cls.__name__.lower()
            b = f"{p}/{name}/"
            routes += [
                Route(b, self._view(ListView, model_cls, admin_cls), methods=["GET"], name=f"admin-{name}-list"),
                Route(f"{b}create/", self._view(CreateView, model_cls, admin_cls), methods=["GET", "POST"], name=f"admin-{name}-create"),
                Route(f"{b}{{id}}/", self._view(DetailView, model_cls, admin_cls), methods=["GET"], name=f"admin-{name}-detail"),
                Route(f"{b}{{id}}/update/", self._view(UpdateView, model_cls, admin_cls), methods=["GET", "POST"], name=f"admin-{name}-update"),
                Route(f"{b}{{id}}/delete/", self._view(DeleteView, model_cls, admin_cls), methods=["GET", "POST"], name=f"admin-{name}-delete"),
            ]
        return routes

    def _view(self, ViewCls, model_cls, admin_cls):
        async def handler(request, response, id=None):
            v = ViewCls(self.site, model_cls, admin_cls)
            if id:
                return await v.handle(request, response, id)
            return await v.handle(request, response)
        return handler

    def _dash(self, ViewCls):
        async def handler(request, response):
            v = ViewCls(self.site)
            return await v.handle(request, response)
        return handler

    def _login(self, ViewCls):
        async def handler(request, response):
            v = ViewCls(self.site)
            return await v.handle(request, response)
        return handler

    async def _logout(self, request, response):
        await self.site.auth.logout(request)
        return response.redirect(f"{self.site.prefix}/login/", status_code=302)
