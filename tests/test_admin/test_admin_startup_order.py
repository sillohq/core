"""
The admin must not care whether it is mounted before or after the database.

A conventional application factory mounts the admin first: ``AdminSite.mount``
attaches auth middleware through ``app.use()``, and middleware ordering forces
it ahead of ``setup_record``. Startup hooks then run in registration order, so
the admin's runs while the ORM is still uninitialised.

Anything the admin decides at startup by asking the ORM a question therefore
gets the wrong answer — and a wrong answer that raises takes the whole
application down with it. These tests boot an application in that order and
assert it comes up.
"""

from pathlib import Path

import pytest
from tortoise import fields

from sillo import silloApp
from sillo.admin import AdminSite
from sillo.record import DatabaseConfig, Model, setup_record
from sillo.users import UserBaseModel


class Widget(Model):
    name = fields.CharField(max_length=50)

    class Meta:
        table = "startup_order_widgets"


class Account(UserBaseModel):
    class Meta:
        table = "startup_order_accounts"


ADMIN_EMAIL = "boss@example.com"
ADMIN_PASSWORD = "Hunter2!pass"


def _app(tmp_path: Path) -> silloApp:
    """Build an application the conventional way: admin first, database second."""
    from sillo.session import SessionConfig, SessionMiddleware

    app = silloApp(title="Order Test")

    admin = AdminSite(title="Order Test", prefix="/admin", user_model=Account)
    admin.mount(app)

    app.use(
        SessionMiddleware(
            config=SessionConfig(session_cookie_secure=False),
            secret_key="test-secret-key",
        )
    )

    setup_record(
        app,
        DatabaseConfig(url=f"sqlite://{tmp_path / 'order.db'}", generate_schemas=True),
        model_modules=[__name__],
    )

    async def seed():
        """Create the administrator inside the startup task.

        Connections are held in a task-scoped context, so a row created from
        outside the application has nowhere to go.
        """
        user = Account(email=ADMIN_EMAIL, username="boss", is_active=True, is_staff=True)
        user.set_password(ADMIN_PASSWORD)
        await user.save()

    app.on_startup(seed)
    return app


def _sign_in(client):
    """Sign the seeded administrator in, returning the response."""
    return client.post(
        "/admin/login/",
        data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        follow_redirects=False,
    )


class TestStartupOrder:
    def test_the_application_starts(self, tmp_path):
        """The regression this file exists for: startup used to fail outright.

        A check for "is the user model registered?" ran in the admin's startup
        hook, before the ORM was up, decided nobody could ever sign in, and
        aborted the boot of every application built this way.
        """
        from sillo.testclient import TestClient

        with TestClient(_app(tmp_path)) as client:
            assert client.get("/admin/login/").status_code == 200

    def test_the_admin_is_usable_once_it_is_up(self, tmp_path):
        from sillo.testclient import TestClient

        with TestClient(_app(tmp_path)) as client:
            signed_in = _sign_in(client)
            assert signed_in.status_code in (302, 303)

            dashboard = client.get("/admin/", cookies=signed_in.cookies)
            assert dashboard.status_code == 200

    def test_a_model_with_no_table_is_absent_rather_than_broken(self, tmp_path):
        """The activity log is registered but its module was not, so it should
        appear nowhere — neither as a sidebar link nor as a dashboard card."""
        from sillo.testclient import TestClient

        with TestClient(_app(tmp_path)) as client:
            signed_in = _sign_in(client)
            dashboard = client.get("/admin/", cookies=signed_in.cookies)

            assert dashboard.status_code == 200
            assert "/admin/adminactivity/" not in dashboard.text
            # The application's own model is registered, so it is offered.
            assert "/admin/account/" in dashboard.text


@pytest.mark.parametrize("model", [Widget, Account])
def test_registered_models_resolve_a_connection_only_once_initialised(model):
    """Outside a connection context there is nothing to resolve, for any model.

    Which is why this question belongs to a request rather than to startup.
    """
    assert AdminSite._model_is_usable(model) is False
