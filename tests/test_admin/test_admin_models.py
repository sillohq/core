"""
Which admin models a project gets, and which it has to ask for.

Model discovery scans a module's namespace, so what these modules contain
decides what tables exist in every project that registers them. An application
that brings its own user model — the ordinary case, since the people who sign
in to the admin are the people who sign in to the application — should not end
up with a second, empty user table it can never write to.
"""

import pytest
from tortoise.models import Model as TortoiseModel


def _discoverable(module) -> set[str]:
    """The concrete models Tortoise would find in *module*'s namespace."""
    return {
        name
        for name, value in vars(module).items()
        if isinstance(value, type)
        and issubclass(value, TortoiseModel)
        and not getattr(getattr(value, "Meta", None), "abstract", False)
        and value is not TortoiseModel
        and getattr(value, "_meta", None) is not None
    }


class TestModelModules:
    def test_registering_the_admin_brings_only_the_activity_log(self):
        """The audit log is what every admin site needs; a user table is not."""
        from sillo.admin import models

        assert _discoverable(models) == {"AdminActivity"}

    def test_the_default_user_model_is_a_separate_module(self):
        """So it is registered on purpose, by projects that actually use it."""
        from sillo.admin import default_user

        assert _discoverable(default_user) == {"AdminRole", "AdminUser"}

    def test_the_admin_package_still_exports_all_of_them(self):
        """Splitting the modules must not change what you can import."""
        from sillo.admin import AdminActivity, AdminRole, AdminUser

        assert AdminUser.__name__ == "AdminUser"
        assert AdminRole.__name__ == "AdminRole"
        assert AdminActivity.__name__ == "AdminActivity"


class TestSharedUserContract:
    def test_the_default_admin_user_is_an_ordinary_user_model(self):
        """Which is what lets an application's own User replace it outright."""
        from sillo.admin import AdminUser
        from sillo.users import UserBaseModel

        assert issubclass(AdminUser, UserBaseModel)

    def test_an_application_user_model_satisfies_the_admin_backend(self):
        """No adapter, no second account: the same class authenticates both."""
        from sillo.admin import AdminSite
        from sillo.users import UserBaseModel

        class AppUser(UserBaseModel):
            class Meta:
                table = "app_users"

        site = AdminSite(user_model=AppUser)

        assert site.auth.user_model is AppUser

    def test_without_one_it_falls_back_to_its_own(self):
        from sillo.admin import AdminSite, AdminUser

        assert AdminSite().auth.user_model is AdminUser


class TestWhoMayEnterTheAdmin:
    """Being signed in is not being an administrator.

    When the admin shares the application's user model, every account that ever
    signed up holds a session. If a session were enough, the sign-up form would
    be the way in.
    """

    def _user(self, **flags):
        from sillo.users import UserBaseModel

        class Account(UserBaseModel):
            class Meta:
                table = "accounts_for_guard_test"

        user = Account(email="a@b.c", username="a")
        for name, value in {
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
            **flags,
        }.items():
            setattr(user, name, value)
        return user

    def test_a_plain_signed_in_account_is_refused(self):
        from sillo.admin.auth import SessionAuth

        assert SessionAuth.may_enter(self._user()) is False

    def test_staff_are_admitted(self):
        from sillo.admin.auth import SessionAuth

        assert SessionAuth.may_enter(self._user(is_staff=True)) is True

    def test_superusers_are_admitted_without_the_staff_flag(self):
        from sillo.admin.auth import SessionAuth

        assert SessionAuth.may_enter(self._user(is_superuser=True)) is True

    def test_a_deactivated_administrator_is_refused(self):
        """Revoking access should not require also clearing is_staff."""
        from sillo.admin.auth import SessionAuth

        assert SessionAuth.may_enter(self._user(is_staff=True, is_active=False)) is False


class TestUnusableModelsAreHiddenNotBroken:
    """An application may keep its database to its own tables.

    The admin registers its own activity log without being told whether the
    application wanted it, so a registered model with no table is a real case.
    Writes to the log already tolerate having nowhere to go; a sidebar link
    leading to a 500 does not.

    The question is asked per request. It cannot be asked at startup: the admin
    mounts before ``setup_record`` in a conventional application factory, so its
    startup hook runs first and the honest answer at that point is always "no".
    """

    def test_a_model_with_no_connection_is_not_usable(self):
        from sillo.admin import AdminActivity, AdminSite

        # Nothing has initialised Tortoise with it in this test.
        assert AdminSite._model_is_usable(AdminActivity) is False

    def test_the_check_resolves_a_connection_rather_than_reading_an_attribute(self):
        """``default_connection`` is populated per connection context.

        Reading it answers differently inside a request and outside one, so a
        check built on it hides the log from a project that registered it.
        """
        from sillo.admin import AdminSite

        class Pretend:
            class _meta:  # noqa: N801 — mirrors Tortoise's attribute name
                db = object()

        assert AdminSite._model_is_usable(Pretend) is True

    def test_the_activity_log_is_still_registered(self):
        """Hidden when unusable, not absent — a project that registers the
        module gets its log without asking for it twice."""
        from sillo.admin import AdminActivity, AdminSite

        site = AdminSite()
        site._register_activity_log()

        assert AdminActivity in site.registry
