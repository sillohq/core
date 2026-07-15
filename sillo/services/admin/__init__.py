"""
sillo.services.admin — Recorder Admin Panel (Django Admin-level).

A full-featured admin interface for sillo applications. Register your
models, customize list displays, add filters, actions, and search — all
with a modern dark-themed UI.

Usage::

    from sillo import silloApp
    from sillo.services.admin import AdminSite, ModelAdmin, setup_admin

    app = silloApp()
    admin = setup_admin(app, title="My App Admin")

    @admin.register(User)
    class UserAdmin(ModelAdmin):
        list_display = ["id", "email", "name", "created_at"]
        search_fields = ["email", "name"]
        list_filter = ["is_active", "plan"]
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Type

from sillo import silloApp
from sillo.routing import Group
from sillo.static import StaticFiles
from .registry import ModelAdmin, Registry
from .auth import AuthBackend, SessionAuth
from .router import AdminRouter


class AdminSite:
    """Central admin site — owns the registry, auth, and router.

    Parameters
    ----------
    title:
        Displayed in the header and browser tab.
    prefix:
        URL prefix for all admin routes (default ``/admin``).
    auth_backend:
        Authentication backend. Defaults to :class:`SessionAuth`.
    """

    def __init__(
        self,
        title: str = "Recorder Admin",
        prefix: str = "/admin",
        auth_backend: Optional[AuthBackend] = None,
    ):
        self.title = title
        self.prefix = prefix.rstrip("/")
        self.registry = Registry()
        self.auth = auth_backend or SessionAuth()
        self.router = AdminRouter(self)
        self._setup = False

    def register(
        self, model_class: Type, admin_class: Optional[Type[ModelAdmin]] = None
    ):
        """Register a model with the admin site.

        Can be used as a decorator or called directly::

            @admin.register(User)
            class UserAdmin(ModelAdmin):
                list_display = ["id", "email"]

            admin.register(Post, PostAdmin)
        """
        if admin_class is None:

            def decorator(kls):
                self.registry.register(model_class, kls)
                return kls

            return decorator

        self.registry.register(model_class, admin_class)
        return admin_class

    def mount(self, app: silloApp) -> None:
        """Register auth middleware, static files, and routes on startup."""
        app.use(self.auth.middleware)
        self._mount_static(app)
        app.on_startup(lambda: self._register_routes(app))
        self._setup = True

    def _mount_static(self, app: silloApp) -> None:
        static_dir = Path(__file__).parent / "static"
        if static_dir.is_dir():
            static_files = StaticFiles(directory=static_dir)
            static_group = Group(path=f"{self.prefix}/static", app=static_files)
            app.router.routes.append(static_group)

    def _register_routes(self, app) -> None:
        for route in self.router.build_routes():
            app.router.add_route(route)


def setup_admin(
    app,
    title: str = "Recorder Admin",
    prefix: str = "/admin",
    auth_backend: Optional[AuthBackend] = None,
) -> AdminSite:
    site = AdminSite(title=title, prefix=prefix, auth_backend=auth_backend)
    site.mount(app)
    return site
