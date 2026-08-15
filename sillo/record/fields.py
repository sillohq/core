"""
sillo.record.fields — Custom Tortoise field types.

- CreatedAtField / UpdatedAtField / SoftDeleteField
- SlugField — auto-generated URL-safe slug
- ULIDField — sortable primary key
"""

from __future__ import annotations

from tortoise import fields as _fields

from sillo.helpers.hashing import hash_password, is_hashed


class PasswordField(_fields.CharField):
    """A CharField that stores a *hashed* password, never the plaintext.

    Declare it on a model like any other field::

        class AdminUser(Model):
            password = PasswordField()

    The admin auto-detects ``PasswordField`` instances and renders a secure
    password widget (reveal toggle, strength meter, confirmation).  Plaintext
    assigned through the ORM is hashed automatically via
    :func:`sillo.helpers.hashing.hash_password` — so ``user.password = "secret"``
    stores a hash, not the raw string.

    Always verify with :func:`sillo.helpers.hashing.verify_password`
    (or the model's ``check_password`` helper) rather than comparing directly.
    """

    password: bool = True

    def __init__(self, max_length: int = 255, **kwargs):
        """Init"""
        kwargs.setdefault("max_length", max_length)
        super().__init__(**kwargs)

    def to_db_value(self, value, instance, *args, **kwargs):
        # Hash plaintext on the way into the database, but leave already-hashed
        # values (those produced by hash_password) untouched.
        """To Db Value"""
        if value is None or value == "":
            return value
        # Asks passlib which scheme produced the value rather than matching a
        # prefix. The prefixes here were bcrypt's alone, so an argon2, scrypt
        # or pbkdf2 hash looked like plaintext and was hashed a second time,
        # and every login against it then failed.
        if is_hashed(value):
            return value
        return hash_password(value)

    def to_python_value(self, value, *args, **kwargs):
        # Never expose the hash as a "python value" that could be re-hashed.
        """To Python Value"""
        return value


class CreatedAtField(_fields.DatetimeField):
    """Auto-set to UTC now on creation. Never updated."""

    def __init__(self, **kwargs):
        """Init"""
        kwargs.setdefault("auto_now_add", True)
        super().__init__(**kwargs)


class UpdatedAtField(_fields.DatetimeField):
    """Auto-set to UTC now on every save."""

    def __init__(self, **kwargs):
        """Init"""
        kwargs.setdefault("auto_now", True)
        super().__init__(**kwargs)


class SoftDeleteField(_fields.DatetimeField):
    """Nullable datetime for soft-deletion. None = active."""

    def __init__(self, **kwargs):
        """Init"""
        kwargs.setdefault("null", True)
        kwargs.setdefault("default", None)
        super().__init__(**kwargs)


class SlugField(_fields.CharField):
    """URL-safe slug, optionally auto-generated from a source field.

    With ``source_field`` set, saving a row that has no slug fills one in from
    that attribute::

        class Post(Model):
            title = fields.CharField(max_length=200)
            slug = SlugField(source_field="title")

        post = await Post.create(title="Hello World")   # slug == "hello-world"

    An explicitly assigned slug is always kept. Generation only ever fills a
    blank, so editing the source later does not silently move a published URL.
    """

    def __init__(
        self, max_length: int = 200, source_field: str | None = None, **kwargs
    ):
        """Init"""
        kwargs.setdefault("max_length", max_length)
        super().__init__(**kwargs)
        self._source_field = source_field

    def to_db_value(self, value, instance, *args, **kwargs):
        """Generate the slug when one was not supplied.

        ``source_field`` used to be stored on the field and read by nothing at
        all, so the documented auto-generation never happened and the argument
        was accepted in silence.
        """
        if not value and self._source_field is not None:
            source = getattr(instance, self._source_field, None)
            if source:
                from sillo.helpers.strings import slugify

                value = slugify(str(source))[: self.max_length]
                # Written back to the instance as well, so the object in hand
                # after `create()` carries the slug the row was given rather
                # than the None it was constructed with.
                if self.model_field_name:
                    setattr(instance, self.model_field_name, value)
        return super().to_db_value(value, instance, *args, **kwargs)


class ULIDField(_fields.CharField):
    """ULID primary key (26-char sortable identifier)."""

    def __init__(self, **kwargs):
        """Init"""
        kwargs.setdefault("max_length", 26)
        kwargs.setdefault("pk", True)
        super().__init__(**kwargs)
