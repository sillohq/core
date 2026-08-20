"""
sillo.storage.policies — who may do what, as an object rather than a flag.

Every other filesystem layer models this as visibility: ``public`` or
``private``.  Two values cannot express the rule most applications actually
want, which is *this user may write under their own prefix and nobody else's* —
so every project writes that by hand, in a handler, next to the upload.  Written
by hand it is forgotten in the second handler.

A policy is asked, per operation, with the user in scope:

    policy.allows(Action.WRITE, "avatars/114/face.png", user)

Four are built in.  :class:`Owned` is the one that pays for the design.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .base import Action

__all__ = ["BucketPolicy", "Owned", "Private", "Public", "ReadOnly", "Signed"]


@runtime_checkable
class BucketPolicy(Protocol):
    """Decides whether one operation is permitted.

    A protocol rather than a base class, so a project's own policy is any
    object with the method — including a closure over its domain model.
    """

    def allows(self, action: Action, key: str, user: Any = None) -> bool:
        """Whether *user* may perform *action* on *key*.

        Args:
            action: What is being attempted.
            key: The object's key, normalised.
            user: The authenticated user, or None.

        Returns:
            True to permit.
        """
        ...

    def signable(self, action: Action) -> bool:
        """Whether a signed URL may grant *action* without a user.

        Separate from :meth:`allows` because a signed URL is exactly the case
        where there is no user to ask about — the permission was decided when
        the URL was minted.

        Args:
            action: What the URL would grant.

        Returns:
            True when a signature is enough on its own.
        """
        ...


class Private:
    """Nothing is permitted without a signature.

    The default, and the right default: a bucket whose contents are reachable
    because nobody thought about it is the failure this whole module is for.
    """

    def allows(self, action: Action, key: str, user: Any = None) -> bool:
        """Refuse everything.

        Args:
            action: Ignored.
            key: Ignored.
            user: Ignored.

        Returns:
            False.
        """
        return False

    def signable(self, action: Action) -> bool:
        """Permit anything a signature was minted for.

        Args:
            action: What the URL grants.

        Returns:
            True.
        """
        return True

    def __repr__(self) -> str:
        """A short description.

        Returns:
            The policy's name.
        """
        return "Private()"


class Public:
    """Anyone may read; only a signature may write.

    Named for what it does rather than what it is called elsewhere.  "Public"
    in most storage layers also means "anybody who finds the URL may overwrite
    it", which is never what anybody meant.
    """

    def allows(self, action: Action, key: str, user: Any = None) -> bool:
        """Permit reads and listings.

        Args:
            action: What is being attempted.
            key: Ignored.
            user: Ignored.

        Returns:
            True for reads and listings.
        """
        return action in (Action.READ, Action.LIST)

    def signable(self, action: Action) -> bool:
        """Permit anything a signature was minted for.

        Args:
            action: What the URL grants.

        Returns:
            True.
        """
        return True

    def __repr__(self) -> str:
        """A short description.

        Returns:
            The policy's name.
        """
        return "Public()"


class ReadOnly:
    """Any authenticated user may read; nobody may write, signed or not.

    For a bucket something else fills — an export target written by a worker
    through the driver directly, and read by people through the application.
    """

    def allows(self, action: Action, key: str, user: Any = None) -> bool:
        """Permit reads by an authenticated user.

        Args:
            action: What is being attempted.
            key: Ignored.
            user: The authenticated user.

        Returns:
            True for reads and listings by somebody signed in.
        """
        return action in (Action.READ, Action.LIST) and _identified(user)

    def signable(self, action: Action) -> bool:
        """Permit signed reads only.

        Args:
            action: What the URL grants.

        Returns:
            True for reads.
        """
        return action is Action.READ

    def __repr__(self) -> str:
        """A short description.

        Returns:
            The policy's name.
        """
        return "ReadOnly()"


class Signed:
    """Only a signature, and only for reading.

    Stricter than :class:`Private`, which will honour a signature for a write.
    """

    def allows(self, action: Action, key: str, user: Any = None) -> bool:
        """Refuse everything unsigned.

        Args:
            action: Ignored.
            key: Ignored.
            user: Ignored.

        Returns:
            False.
        """
        return False

    def signable(self, action: Action) -> bool:
        """Permit signed reads only.

        Args:
            action: What the URL grants.

        Returns:
            True for reads.
        """
        return action is Action.READ

    def __repr__(self) -> str:
        """A short description.

        Returns:
            The policy's name.
        """
        return "Signed()"


class Owned:
    """A user may do as they like under their own prefix, and nothing outside it.

    The rule most applications actually want and no visibility flag can state.
    ``avatars/{id}/`` gives every user a private area of one shared bucket, and
    the check happens on every operation rather than in whichever handler
    remembered it.

    Attributes:
        prefix: A template with one placeholder, ``{id}``.
        readable: Whether users may read each other's objects. Off by default,
            because a shared bucket where everybody can read everything is a
            shared bucket, not a private area.
    """

    __slots__ = ("prefix", "readable")

    def __init__(self, prefix: str = "{id}/", *, readable: bool = False) -> None:
        """Build the policy.

        Args:
            prefix: Where a user's own objects live.
            readable: Whether users may read outside their own prefix.

        Raises:
            ValueError: If the prefix has no placeholder — which would give
                every user the same area and quietly make the bucket shared.
        """
        if "{id}" not in prefix:
            raise ValueError(
                "an Owned prefix must contain {id}, or every user shares one area"
            )

        self.prefix = prefix
        self.readable = readable

    def allows(self, action: Action, key: str, user: Any = None) -> bool:
        """Permit operations inside the user's own prefix.

        Args:
            action: What is being attempted.
            key: The object's key.
            user: The authenticated user.

        Returns:
            True when the key is the user's own, or when reading is open.
        """
        if not _identified(user):
            return False

        if key.startswith(self.prefix.format(id=_identity(user))):
            return True

        return self.readable and action in (Action.READ, Action.LIST)

    def signable(self, action: Action) -> bool:
        """Permit anything a signature was minted for.

        Args:
            action: What the URL grants.

        Returns:
            True. A signature for this bucket was minted by the application,
            which had already decided whose object it was.
        """
        return True

    def area(self, user: Any) -> str:
        """Where one user's objects live.

        Args:
            user: The authenticated user.

        Returns:
            Their prefix.
        """
        return self.prefix.format(id=_identity(user))

    def __repr__(self) -> str:
        """A short description.

        Returns:
            The prefix and whether reads are open.
        """
        return f"Owned(prefix={self.prefix!r}, readable={self.readable})"


def _identified(user: Any) -> bool:
    """Whether there is a signed-in user.

    Reads ``is_authenticated``, which is what sillo's ``UserBaseModel`` exposes
    and what ``UnauthenticatedUser`` answers False to — so an anonymous request
    carries a user object and is still correctly refused.

    Args:
        user: Whatever was in scope.

    Returns:
        True when somebody is signed in.
    """
    return user is not None and bool(getattr(user, "is_authenticated", False))


def _identity(user: Any) -> str:
    """A stable identifier for a user.

    Args:
        user: The authenticated user.

    Returns:
        Their ``identity``, ``id``, or ``str()``.
    """
    return str(getattr(user, "identity", None) or getattr(user, "id", None) or user)
