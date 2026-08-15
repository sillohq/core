"""Regressions for defects that shipped in 0.1.0b1.

Each of these was a feature that looked present and did nothing, or did
something weaker than its name promised. None of them had a test, which is why
they survived: the ORM has no way to notice that a column named ``encrypted``
holds recoverable plaintext, or that a ``source_field`` argument is stored and
never read.
"""

import inspect

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model
from sillo.record.fields import PasswordField, SlugField

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)

CAST_KEY = "unit-test-passphrase"


class Article(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200)
    slug = SlugField(source_field="title", null=True)
    secret = fields.TextField(null=True)
    meta = fields.TextField(null=True)

    _casts = {
        "secret": ("encrypted", {"key": CAST_KEY}),
        "meta": "json",
    }

    class Meta:
        table = "release_fix_articles"


class Account(Model):
    id = fields.IntField(pk=True)
    password = PasswordField()

    class Meta:
        table = "release_fix_accounts"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record.test_release_fixes"]},
    )
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas()
    yield
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass


class TestEncryptedCast:
    """It was XOR against a repeating key, so the column was readable."""

    async def test_round_trips_through_the_database(self):
        await Article.create(title="A", secret="sk_live_abc123")
        found = await Article.get(title="A")
        assert found.secret == "sk_live_abc123"

    async def test_the_stored_column_does_not_contain_the_plaintext(self):
        await Article.create(title="A", secret="sk_live_abc123")
        raw = (await Article.all().values("secret"))[0]["secret"]
        assert "sk_live_abc123" not in raw

    async def test_two_writes_of_one_value_differ(self):
        # Fernet carries a per-message IV. Identical ciphertext for identical
        # plaintext would leak which rows share a secret.
        await Article.create(title="A", secret="same")
        await Article.create(title="B", secret="same")
        stored = [row["secret"] for row in await Article.all().values("secret")]
        assert stored[0] != stored[1]

    async def test_a_wrong_key_cannot_read_it(self):
        from sillo.record.casting import _encrypted_factory

        encode, _ = _encrypted_factory(CAST_KEY)
        _, decode_other = _encrypted_factory("a-different-passphrase")
        with pytest.raises(Exception):
            decode_other(encode("sk_live_abc123"))


class TestSlugField:
    """``source_field`` was stored on the field and read by nothing."""

    async def test_generates_a_slug_from_the_source_field(self):
        article = await Article.create(title="Hello World Again")
        assert article.slug == "hello-world-again"

    async def test_keeps_an_explicit_slug(self):
        article = await Article.create(title="Hello World", slug="custom-slug")
        assert article.slug == "custom-slug"

    async def test_survives_a_reload(self):
        await Article.create(title="Round Trip")
        assert (await Article.get(title="Round Trip")).slug == "round-trip"


class TestPasswordField:
    """The already-hashed check only ever recognised bcrypt."""

    @pytest.mark.parametrize("scheme", ["bcrypt", "pbkdf2_sha256"])
    async def test_an_existing_hash_is_not_hashed_again(self, scheme):
        from sillo.helpers.hashing import verify_password
        from sillo.hashing import hash_password

        hashed = hash_password("correct horse", scheme=scheme)
        account = await Account.create(password=hashed)
        stored = (await Account.get(id=account.id)).password
        assert stored == hashed
        assert verify_password("correct horse", stored)

    async def test_plaintext_is_still_hashed(self):
        from sillo.helpers.hashing import verify_password

        account = await Account.create(password="correct horse")
        stored = (await Account.get(id=account.id)).password
        assert stored != "correct horse"
        assert verify_password("correct horse", stored)


class TestQuerySetUpdateAppliesCasts:
    """`save()` encoded cast fields; `.filter(...).update()` did not."""

    async def test_json_cast_is_applied(self):
        await Article.create(title="A", meta={"a": 1})
        await Article.filter(title="A").update(meta={"b": 2})
        assert (await Article.get(title="A")).meta == {"b": 2}

    async def test_the_column_holds_json_not_a_python_repr(self):
        await Article.create(title="A", meta={"a": 1})
        await Article.filter(title="A").update(meta={"b": 2})
        raw = (await Article.all().values("meta"))[0]["meta"]
        assert raw == '{"b": 2}'

    async def test_encrypted_cast_is_applied(self):
        await Article.create(title="A", secret="first")
        await Article.filter(title="A").update(secret="second")
        raw = (await Article.all().values("secret"))[0]["secret"]
        assert "second" not in raw
        assert (await Article.get(title="A")).secret == "second"

    async def test_uncast_fields_are_untouched(self):
        await Article.create(title="A")
        await Article.filter(title="A").update(title="B")
        assert await Article.filter(title="B").count() == 1
