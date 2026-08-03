"""
Which admin models a project gets, and which it has to ask for.

Model discovery scans a module's namespace, so what these modules contain
decides what tables exist in every project that registers them. An application
that brings its own user model — the ordinary case, since the people who sign
in to the admin are the people who sign in to the application — should not end
up with a second, empty user table it can never write to.
"""

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
