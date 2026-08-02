from sillo.hashing import (
    is_password_usable,
    needs_update,
    password_strength,
    validate_password,
)
from sillo.users.base import (
    UserProtocol,
    UserBaseModel,
    AnonymousUser,
    BaseUser,
    User,
    check_password,
    make_password,
)
from sillo.users.managers import UserManager
from sillo.users.simple import SimpleUser, UnauthenticatedUser

__all__ = [
    "UserProtocol",
    "UserBaseModel",
    "BaseUser",
    "AnonymousUser",
    "User",
    "UserManager",
    "SimpleUser",
    "UnauthenticatedUser",
    "make_password",
    "check_password",
    "is_password_usable",
    "needs_update",
    "validate_password",
    "password_strength",
]

# Management operations as plain functions, for a project's own tooling to
# call. sillo ships no CLI; sillo-start and your scripts consume these.
from sillo.users import commands  # noqa: E402,F401
