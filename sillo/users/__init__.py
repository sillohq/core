"""
sillo.users — user models, the authentication contract, and account helpers.

The database-backed models are loaded on demand. ``sillo.users.base`` defines
Tortoise models, so importing it eagerly would make ``import sillo`` require the
``record`` extra; a module-level ``__getattr__`` defers that until one of those
names is actually asked for. Everything that needs no database — the protocol,
the anonymous and simple users, the password helpers — imports normally.

The public names are unchanged. ``from sillo.users import User`` still works,
and raises the ORM's own ImportError when the extra is missing.
"""

from sillo._internals.lazy import deferred
from sillo.hashing import (
    is_password_usable,
    needs_update,
    password_strength,
    validate_password,
)
from sillo.users.managers import UserManager
from sillo.users.protocol import (
    AnonymousUser,
    BaseUser,
    UserProtocol,
    check_password,
    make_password,
)
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

#: Names that live on a Tortoise model, so they need the `record` extra.
__getattr__ = deferred(__name__, {"User": ".base", "UserBaseModel": ".base"})


# Management operations as plain functions, for a project's own tooling to
# call. They resolve the user model lazily, so importing this costs nothing.
from sillo.users import commands  # noqa: E402,F401
