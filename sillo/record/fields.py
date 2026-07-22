"""
sillo.record.fields — Custom Tortoise field types.

- CreatedAtField / UpdatedAtField / SoftDeleteField
- SlugField — auto-generated URL-safe slug
- ULIDField — sortable primary key
"""

from __future__ import annotations

from typing import Optional

from tortoise import fields as _fields

from sillo.helpers.hashing import hash_password


class PasswordField(_fields.CharField):
    """A CharField that stores a *hashed* password, never the plaintext.

    Declare it on a model like any other field::

        class AdminUser(Model):
            password = PasswordField()

    The admin auto-detects ``PasswordField`` instances and renders a secure
    password widget (reveal toggle, strength meter, confirmation).  Plaintext
    assigned through the ORM is hashed automatically via
    :func:`sillo.helpers.hashing.hash_password` — so ``user.password = "secret"``
    stores a bcrypt hash, not the raw string.

    Always verify with :func:`sillo.helpers.hashing.verify_password`
    (or the model's ``check_password`` helper) rather than comparing directly.
    """

    password: bool = True

    def __init__(self, max_length: int = 255, **kwargs):
        """Init

            Args:
                max_length: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        kwargs.setdefault("max_length", max_length)
        super().__init__(**kwargs)

    def to_db_value(self, value, instance, *args, **kwargs):
        # Hash plaintext on the way into the database, but leave already-hashed
        # values (those produced by hash_password) untouched.
        """To Db Value

            Args:
                value: [description]
                instance: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        if value is None or value == "":
            return value
        if isinstance(value, str) and value.startswith(("$2b$", "$2a$", "$2y$")):
            return value  # already a bcrypt hash
        return hash_password(value)

    def to_python_value(self, value, *args, **kwargs):
        # Never expose the hash as a "python value" that could be re-hashed.
        """To Python Value

            Args:
                value: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return value


class CreatedAtField(_fields.DatetimeField):
    """Auto-set to UTC now on creation. Never updated."""

    def __init__(self, **kwargs):
        """Init

            Returns:
                [description]

            Raises:
                [description]
        """
        kwargs.setdefault("auto_now_add", True)
        super().__init__(**kwargs)


class UpdatedAtField(_fields.DatetimeField):
    """Auto-set to UTC now on every save."""

    def __init__(self, **kwargs):
        """Init

            Returns:
                [description]

            Raises:
                [description]
        """
        kwargs.setdefault("auto_now", True)
        super().__init__(**kwargs)


class SoftDeleteField(_fields.DatetimeField):
    """Nullable datetime for soft-deletion. None = active."""

    def __init__(self, **kwargs):
        """Init

            Returns:
                [description]

            Raises:
                [description]
        """
        kwargs.setdefault("null", True)
        kwargs.setdefault("default", None)
        super().__init__(**kwargs)


class SlugField(_fields.CharField):
    """URL-safe slug, optionally auto-generated from a source field."""

    def __init__(
        self, max_length: int = 200, source_field: Optional[str] = None, **kwargs
    ):
        """Init

            Args:
                max_length: [description]
                source_field: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        kwargs.setdefault("max_length", max_length)
        super().__init__(**kwargs)
        self._source_field = source_field


class ULIDField(_fields.CharField):
    """ULID primary key (26-char sortable identifier)."""

    def __init__(self, **kwargs):
        """Init

            Returns:
                [description]

            Raises:
                [description]
        """
        kwargs.setdefault("max_length", 26)
        kwargs.setdefault("pk", True)
        super().__init__(**kwargs)
