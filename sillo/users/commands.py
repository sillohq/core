"""User management, as functions.

These are the operations a command line
expose, written as plain async functions so that a project's own tooling —
``sillo-start``, a Click group, a management script, a test — can call them
without going through a process boundary.

Each takes the user model explicitly rather than reaching for a global, so an
application with its own ``User`` subclass is served by the same functions as
one using the built-in.

Usage::

    from sillo.users.commands import create_admin

    user = await create_admin("ada@example.com", "ada", "Str0ng!pass")

Every function assumes the ORM is already initialised — ``setup_record`` during
application startup, or ``Tortoise.init`` in a script.
"""

from __future__ import annotations

from typing import Annotated, Any, List, Optional

from typing_extensions import Doc

UserModel = Any


def _resolve(model: UserModel = None) -> UserModel:
    """Return *model*, or the built-in user model when none was given."""
    if model is not None:
        return model
    from sillo.users.base import User

    return User


async def create_user(
    email: Annotated[str, Doc("Email address. Must not already be registered.")],
    username: Annotated[str, Doc("Username. Must not already be taken.")],
    password: Annotated[str, Doc("Plain-text password; hashed before storage.")],
    *,
    model: Annotated[UserModel, Doc("User model. Defaults to sillo's.")] = None,
    **fields: Annotated[Any, Doc("Extra columns to set on the new row.")],
) -> UserModel:
    """Create an ordinary user.

    Returns:
        The created user.

    Raises:
        ValueError: If the email or username is taken, or the password fails
            the policy — at least 8 characters, with an uppercase letter, a
            digit and a special character.
    """
    user_model = _resolve(model)
    await _refuse_duplicates(user_model, email, username)
    return await user_model.objects.create_user(
        email=email, username=username, password=password, **fields
    )


async def create_admin(
    email: Annotated[str, Doc("Email address. Must not already be registered.")],
    username: Annotated[str, Doc("Username. Must not already be taken.")],
    password: Annotated[str, Doc("Plain-text password; hashed before storage.")],
    *,
    model: Annotated[UserModel, Doc("User model. Defaults to sillo's.")] = None,
    **fields: Annotated[Any, Doc("Extra columns to set on the new row.")],
) -> UserModel:
    """Create a user who can reach the admin panel.

    The admin authenticates against the project's own user model and admits
    accounts marked ``is_staff``, which ``create_superuser`` sets.

    Returns:
        The created user.

    Raises:
        ValueError: As :func:`create_user`.
    """
    user_model = _resolve(model)
    await _refuse_duplicates(user_model, email, username)
    return await user_model.objects.create_superuser(
        email=email, username=username, password=password, **fields
    )


async def _refuse_duplicates(model: UserModel, email: str, username: str) -> None:
    """Fail before writing when the email or username is already in use.

    Letting the database constraint raise would surface as an integrity error
    naming a column, rather than saying which value was the problem.

    Raises:
        ValueError: If either is taken.
    """
    if await model.objects.get_by_email(email) is not None:
        raise ValueError(f"{email} is already registered.")
    if await model.objects.get_by_username(username) is not None:
        raise ValueError(f"The username {username!r} is taken.")


async def find_user(
    identifier: Annotated[str, Doc("Email address or username.")],
    *,
    model: Annotated[UserModel, Doc("User model. Defaults to sillo's.")] = None,
    include_inactive: Annotated[bool, Doc("Match deactivated accounts too.")] = True,
) -> Optional[UserModel]:
    """Look a user up by either of the things people know them by.

    Queries the model directly rather than through ``objects.get_by_email``,
    which filters on ``is_active`` — administering an account means reaching
    the deactivated ones too, and a deactivated user you cannot find is a
    user you can never turn back on.

    Args:
        include_inactive: Set False to match only accounts that may sign in.

    Returns:
        The user, or None when nothing matches.
    """
    user_model = _resolve(model)
    query = user_model.filter(email=identifier)
    if not include_inactive:
        query = query.filter(is_active=True)
    found = await query.first()
    if found is not None:
        return found

    query = user_model.filter(username=identifier)
    if not include_inactive:
        query = query.filter(is_active=True)
    return await query.first()


async def set_password(
    identifier: Annotated[str, Doc("Email address or username.")],
    password: Annotated[str, Doc("The new plain-text password.")],
    *,
    model: Annotated[UserModel, Doc("User model. Defaults to sillo's.")] = None,
) -> UserModel:
    """Change a user's password.

    Returns:
        The updated user.

    Raises:
        LookupError: If no user matches *identifier*.
        ValueError: If the password fails the policy.
    """
    user = await _require(identifier, model)
    user.set_password(password)
    await user.save()
    return user


async def set_active(
    identifier: Annotated[str, Doc("Email address or username.")],
    active: Annotated[bool, Doc("Whether the account may sign in.")],
    *,
    model: Annotated[UserModel, Doc("User model. Defaults to sillo's.")] = None,
) -> UserModel:
    """Enable or disable an account.

    Deactivating is the reversible alternative to deleting: credentials stop
    working immediately and the rows that reference the user stay valid.

    Returns:
        The updated user.

    Raises:
        LookupError: If no user matches *identifier*.
    """
    user = await _require(identifier, model)
    user.is_active = active
    await user.save()
    return user


async def set_staff(
    identifier: Annotated[str, Doc("Email address or username.")],
    staff: Annotated[bool, Doc("Whether the account may reach the admin.")],
    *,
    model: Annotated[UserModel, Doc("User model. Defaults to sillo's.")] = None,
) -> UserModel:
    """Grant or withdraw admin access.

    Returns:
        The updated user.

    Raises:
        LookupError: If no user matches *identifier*.
    """
    user = await _require(identifier, model)
    user.is_staff = staff
    await user.save()
    return user


async def list_users(
    *,
    model: Annotated[UserModel, Doc("User model. Defaults to sillo's.")] = None,
    limit: Annotated[int, Doc("Maximum rows to return.")] = 50,
    offset: Annotated[int, Doc("Rows to skip.")] = 0,
    staff_only: Annotated[bool, Doc("Only accounts with admin access.")] = False,
) -> List[UserModel]:
    """List users, newest first.

    Returns:
        Up to *limit* users.
    """
    user_model = _resolve(model)
    query = user_model.filter(is_staff=True) if staff_only else user_model.all()
    return await query.order_by("-id").offset(offset).limit(limit)


async def _require(identifier: str, model: UserModel) -> UserModel:
    """Find a user or say plainly that there isn't one.

    Raises:
        LookupError: If nothing matches.
    """
    user = await find_user(identifier, model=model)
    if user is None:
        raise LookupError(f"No user matches {identifier!r}.")
    return user
