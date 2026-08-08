"""
sillo.admin — Recorder Admin Panel (Django Admin-level).

A full-featured admin interface for sillo applications. Register your
models, customize list displays, add filters, actions, and search — all
with a modern dark-themed UI.

Usage::

    from sillo import silloApp
    from sillo.admin import AdminSite, ModelAdmin, setup_admin

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
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Type

if TYPE_CHECKING:
    from sillo import silloApp

from sillo.core.routing import Group
from sillo.static import StaticFiles

from .auth import AuthBackend, SessionAuth
from .default_user import AdminRole, AdminUser
from .models import AdminActivity
from .registry import ModelAdmin, Registry
from .router import build_routes


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
    user_model:
        Model backing admin login — any subclass of
        :class:`sillo.users.UserBaseModel`. Defaults to :class:`AdminUser`.
        Ignored if ``auth_backend`` is passed explicitly (build your own
        ``SessionAuth(user_model=...)`` there instead).
    """

    def __init__(
        self,
        title: str = "Recorder Admin",
        prefix: str = "/admin",
        auth_backend: AuthBackend | None = None,
        user_model: type | None = None,
    ):
        """Init"""
        self.title = title
        self.prefix = prefix.rstrip("/")
        self.registry = Registry()
        self.auth = auth_backend or SessionAuth(user_model=user_model or AdminUser)
        self._build_routes = build_routes
        self._setup = False

    def register(self, model_class: type, admin_class: type[ModelAdmin] | None = None):
        """Register a model with the admin site.

        Can be used as a decorator or called directly::

            @admin.register(User)
            class UserAdmin(ModelAdmin):
                list_display = ["id", "email"]

            admin.register(Post, PostAdmin)
        """
        if admin_class is None:

            def decorator(kls):
                """Decorator"""
                self.registry.register(model_class, kls)
                return kls

            return decorator

        self.registry.register(model_class, admin_class)
        return admin_class

    def mount(self, app: silloApp) -> None:
        """Register auth middleware, static files, and routes on startup."""
        self._register_system_models()
        self._register_activity_log()
        app.use(self.auth.middleware)
        self._mount_static(app)
        app.on_startup(lambda: self._register_routes(app))  # ty: ignore[invalid-argument-type]
        self._setup = True

    def _register_system_models(self) -> None:
        """Register the configured user model.

        Every admin site needs a way to browse who can log in, and the user
        model is always usable — the site cannot authenticate without it.
        Roles/permissions (``AdminRole``) are deliberately NOT auto-registered
        here; register those yourself if you use them.
        """
        user_model = getattr(self.auth, "user_model", None)
        if user_model is not None and user_model not in self.registry:

            class _AuthAdmin(ModelAdmin):
                verbose_name = "Auth"
                list_display: ClassVar[list[str]] = [
                    "id",
                    "email",
                    "username",
                    "is_active",
                    "is_superuser",
                ]
                search_fields: ClassVar[list[str]] = ["email", "username"]

            self.registry.register(user_model, _AuthAdmin)

    def _register_activity_log(self) -> None:
        """Register the activity log so it can be browsed.

        Whether it is *usable* — whether the application registered
        ``sillo.admin.models`` at all — is not asked here. It cannot be: this
        runs before the ORM is initialised, and the honest answer at this point
        is always "no". The sidebar asks instead, per request, by which time
        there is something to ask.
        """
        if AdminActivity not in self.registry:

            class _ActivityAdmin(ModelAdmin):
                verbose_name = "Activity Log"
                list_display: ClassVar[list[str]] = [
                    "id",
                    "user_email",
                    "action",
                    "model_name",
                    "created_at",
                ]
                search_fields: ClassVar[list[str]] = [
                    "user_email",
                    "action",
                    "model_name",
                ]
                ordering: ClassVar[list[str]] = ["-created_at"]

            self.registry.register(AdminActivity, _ActivityAdmin)

    def _mount_static(self, app: silloApp) -> None:
        """Mount Static"""
        static_dir = Path(__file__).parent / "static"
        if static_dir.is_dir():
            static_files = StaticFiles(directory=static_dir)
            static_group = Group(path=f"{self.prefix}/static", app=static_files)
            app.router.routes.append(static_group)

    @staticmethod
    def _model_is_usable(model) -> bool:
        """Whether *model* can be queried right now.

        Asked by resolving the connection the way a query would, rather than by
        reading ``default_connection``: that attribute is populated per
        connection context, so it reads empty outside a request and populated
        inside one, and a check built on it answers differently depending on
        where it is called from.

        A model the application never registered has no connection to resolve,
        which is the same failure its list page would hit.
        """
        try:
            return model._meta.db is not None
        except Exception:
            return False

    def _register_routes(self, app) -> None:
        """Build and attach the admin's routes."""
        for route in self._build_routes(self):
            app.router.add_route(route)


def setup_admin(
    app,
    title: str = "Recorder Admin",
    prefix: str = "/admin",
    auth_backend: AuthBackend | None = None,
    user_model: type | None = None,
) -> AdminSite:
    """Build an admin site and mount it on the application.

    Args:
        app: The application to mount the admin on.
        title: Name shown in the admin's own header and page titles.
        prefix: Path the admin is served under. Its routes all carry a
            trailing slash, so ``/admin/`` rather than ``/admin``.
        auth_backend: Backend used to authenticate admin logins. Defaults to
            session authentication against ``user_model``.
        user_model: Subclass of :class:`sillo.users.UserBaseModel` to
            authenticate admin logins against. Defaults to :class:`AdminUser`.
            Build your own to add fields or change RBAC, e.g.::

                class MyAdminUser(UserBaseModel):
                    department = fields.CharField(max_length=100, null=True)
                    class Meta:
                        table = "my_admin_users"

                admin = setup_admin(app, user_model=MyAdminUser)
    """
    site = AdminSite(
        title=title, prefix=prefix, auth_backend=auth_backend, user_model=user_model
    )
    site.mount(app)
    return site
