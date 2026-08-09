"""Django-admin-level tests for sillo.admin.

Covers: hashed-password login, password fields (hashing + confirmation +
mismatch/short rejection), M2M persistence with visual chips, O2O/FK
combobox persistence, list filters, bulk actions, reverse relations on the
detail page, permission redirects, and activity logging.

Run with pytest. Each test builds a fresh app + sqlite file so state never
leaks. The sync TestClient runs the app (and Tortoise) in a background event
loop; DB queries are executed in that same loop via `client.portal.call`, and
the admin session cookie is extracted from the login response and replayed on
authenticated requests.
"""

import pytest
from tortoise import Tortoise, fields

from sillo import SilloApp
from sillo.record import Model, setup_record, DatabaseConfig
from sillo.record.fields import PasswordField
from sillo.session import SessionMiddleware, SessionConfig
from sillo.admin import setup_admin, ModelAdmin
from sillo.admin.default_user import AdminRole, AdminUser
from sillo.admin.models import AdminActivity
from sillo.helpers.hashing import verify_password
from sillo.testclient import TestClient


class Author(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=120)
    email = fields.CharField(max_length=255, null=True)
    is_active = fields.BooleanField(default=True)
    bio = fields.TextField(null=True)

    def __str__(self):
        return self.name


class Tag(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=80, unique=True)

    def __str__(self):
        return self.name


class Book(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200)
    author: fields.ForeignKeyRelation[Author] = fields.ForeignKeyField(
        "models.Author", related_name="books"
    )
    tags: fields.ManyToManyRelation[Tag] = fields.ManyToManyField("models.Tag")

    def __str__(self):
        return self.title


class Profile(Model):
    id = fields.IntField(pk=True)
    bio = fields.TextField(null=True)
    author: fields.OneToOneRelation[Author] = fields.OneToOneField(
        "models.Author", related_name="profile"
    )

    def __str__(self):
        return f"Profile({self.author_id})"


class Account(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=100, unique=True)
    password = PasswordField()


class AuthorAdmin(ModelAdmin):
    list_display = ["id", "name", "email", "is_active"]
    search_fields = ["name", "email"]
    list_filter = ["is_active"]
    ordering = ["-id"]


class BookAdmin(ModelAdmin):
    list_display = ["id", "title", "author_id", "created_at"]
    search_fields = ["title"]
    list_filter = ["author_id"]


class TagAdmin(ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


class ProfileAdmin(ModelAdmin):
    list_display = ["id", "author_id"]


class AccountAdmin(ModelAdmin):
    list_display = ["id", "username"]


def _make_app(db_path):
    app = SilloApp(title="Admin Test")
    setup_record(
        app,
        DatabaseConfig.sqlite(str(db_path)),
        model_modules=["sillo.admin.models", "sillo.admin.default_user", __name__],
    )
    admin = setup_admin(app, title="Admin Test", prefix="/admin")

    @admin.register(Author)
    class _AuthorAdmin(AuthorAdmin):
        pass

    @admin.register(Book)
    class _BookAdmin(BookAdmin):
        pass

    @admin.register(Tag)
    class _TagAdmin(TagAdmin):
        pass

    @admin.register(Profile)
    class _ProfileAdmin(ProfileAdmin):
        pass

    @admin.register(Account)
    class _AccountAdmin(AccountAdmin):
        pass

    # AdminUser / AdminActivity are auto-registered by setup_admin() itself —
    # no manual @admin.register() needed (see AdminSite._register_system_models).

    @app.on_startup
    async def _seed():
        role = await AdminRole.get_or_none(slug="super")
        if not role:
            role = await AdminRole.create(
                name="Super", slug="super", permissions=["*"]
            )
        if not await AdminUser.get_or_none(email="admin@test.com"):
            await AdminUser.create(
                email="admin@test.com",
                username="admin",
                password="admin",
                is_active=True,
                is_superuser=True,
                role=role,
            )

    # SessionMiddleware is added LAST so it is inserted at the front of the
    # chain and runs before the admin auth middleware (which reads the session).
    # secure=False keeps the cookie replayable over the http test transport.
    app.use(
        SessionMiddleware(
            config=SessionConfig(session_cookie_secure=False),
            secret_key="test-secret-key",
        )
    )
    return app


def _run(client, coro_factory):
    """Run a coroutine (returned by coro_factory) inside the app's event loop."""
    return client.portal.call(coro_factory)


@pytest.fixture
def client(tmp_path):
    app = _make_app(tmp_path / "test.db")
    with TestClient(app) as c:
        db = app.state.get("record")
        ctx = db._root_context if db is not None else None
        # Tortoise >=1.0 uses per-task contextvars.  Enter the context from
        # the main thread so that portal.call() tasks inherit it.  This is
        # safe for Tortoise 0.x too where _root_context is None.
        if ctx is not None:
            ctx.__enter__()
        try:
            yield c
        finally:
            try:
                c.portal.call(Tortoise._drop_databases)
            except Exception:
                pass
            finally:
                if ctx is not None:
                    ctx.__exit__(None, None, None)


def _login(client):
    resp = client.post(
        "/admin/login/",
        data={"email": "admin@test.com", "password": "admin"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), (resp.status_code, resp.text[:300])
    return client.cookies.get("session_id")


def _auth_get(client, cookie, url):
    return client.get(url, cookies={"session_id": cookie})


def test_login_page_renders(client):
    resp = client.get("/admin/login/")
    assert resp.status_code == 200
    assert b"Sign in" in resp.content


def test_unauthenticated_list_redirects(client):
    resp = client.get("/admin/author/", follow_redirects=False)
    assert resp.status_code in (301, 302, 303)
    assert "/admin/login" in resp.headers.get("location", "")


def test_login_with_wrong_password_fails(client):
    resp = client.post(
        "/admin/login/",
        data={"email": "admin@test.com", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert b"Invalid credentials" in resp.content


def test_login_success_and_dashboard(client):
    cookie = _login(client)
    resp = _auth_get(client, cookie, "/admin/")
    assert resp.status_code == 200
    assert b"Dashboard" in resp.content


def test_create_and_list_author(client):
    cookie = _login(client)
    resp = client.post(
        "/admin/author/create/",
        data={"name": "Ada Lovelace", "email": "ada@x.com", "is_active": "1"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text
    author = _run(client, lambda: Author.get_or_none(name="Ada Lovelace"))
    assert author is not None
    assert author.name == "Ada Lovelace"


def test_update_author(client):
    cookie = _login(client)
    author = _run(client, lambda: Author.create(name="Grace", email="g@x.com"))
    resp = client.post(
        f"/admin/author/{author.id}/update/",
        data={"name": "Grace Hopper", "email": "grace@x.com", "is_active": "1"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text
    refreshed = _run(client, lambda: Author.get(id=author.id))
    assert refreshed.name == "Grace Hopper"


def test_delete_author(client):
    cookie = _login(client)
    author = _run(client, lambda: Author.create(name="Delete Me", email="d@x.com"))
    resp = client.post(
        f"/admin/author/{author.id}/delete/", data={}, follow_redirects=False
    )
    assert resp.status_code in (302, 303)
    assert _run(client, lambda: Author.get_or_none(id=author.id)) is None


def test_password_field_hashes_and_requires_confirm(client):
    cookie = _login(client)
    resp = client.post(
        "/admin/account/create/",
        data={
            "username": "alice",
            "password": "supersecret1",
            "password__confirm": "supersecret1",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text
    acc = _run(client, lambda: Account.get_or_none(username="alice"))
    assert acc is not None
    assert "supersecret1" not in acc.password
    assert verify_password("supersecret1", acc.password)
    assert not verify_password("other", acc.password)


def test_password_mismatch_rejected(client):
    cookie = _login(client)
    resp = client.post(
        "/admin/account/create/",
        data={
            "username": "bob",
            "password": "aaaaaaaa",
            "password__confirm": "bbbbbbbb",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert b"Passwords do not match" in resp.content
    assert _run(client, lambda: Account.get_or_none(username="bob")) is None


def test_password_too_short_rejected(client):
    cookie = _login(client)
    resp = client.post(
        "/admin/account/create/",
        data={
            "username": "carol",
            "password": "short",
            "password__confirm": "short",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert b"at least 8 characters" in resp.content


def test_password_change_on_update_optional(client):
    cookie = _login(client)
    acc = _run(client, lambda: Account.create(username="dave", password="initialpass1"))
    resp = client.post(
        f"/admin/account/{acc.id}/update/",
        data={"username": "dave2"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text
    refreshed = _run(client, lambda: Account.get(id=acc.id))
    assert refreshed.username == "dave2"
    assert verify_password("initialpass1", refreshed.password)


def test_adminuser_check_password(client):
    cookie = _login(client)
    u = _run(client, lambda: AdminUser.get_or_none(email="admin@test.com"))
    assert u is not None
    assert u.check_password("admin") is True
    assert u.check_password("nope") is False


def test_m2m_create_and_update_persists(client):
    cookie = _login(client)
    t1 = _run(client, lambda: Tag.create(name="python"))
    t2 = _run(client, lambda: Tag.create(name="async"))
    author = _run(client, lambda: Author.create(name="Writer", email="w@x.com"))

    resp = client.post(
        "/admin/book/create/",
        data=[
            ("title", "Async Python"),
            ("author", str(author.id)),
            ("tags", str(t1.id)),
            ("tags", str(t2.id)),
        ],
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text

    book = _run(client, lambda: Book.get_or_none(title="Async Python"))
    assert book is not None
    assert _run(client, lambda: book.tags.all().count()) == 2

    resp = client.post(
        f"/admin/book/{book.id}/update/",
        data=[
            ("title", "Async Python 2"),
            ("author", str(author.id)),
            ("tags", str(t1.id)),
        ],
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text
    book = _run(client, lambda: Book.get(id=book.id))
    assert _run(client, lambda: book.tags.all().count()) == 1


def test_o2o_and_fk_persist(client):
    cookie = _login(client)
    author = _run(client, lambda: Author.create(name="Linked", email="l@x.com"))
    resp = client.post(
        "/admin/profile/create/",
        data=[("author", str(author.id)), ("bio", "my bio")],
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text
    prof = _run(client, lambda: Profile.get_or_none(bio="my bio"))
    assert prof is not None
    assert prof.author_id == author.id


def test_list_filter_applies(client):
    cookie = _login(client)
    _run(client, lambda: Author.create(name="Active One", email="a1@x.com", is_active=True))
    _run(client, lambda: Author.create(name="Inactive One", email="a2@x.com", is_active=False))
    resp = _auth_get(client, cookie, "/admin/author/?f_is_active=0")
    assert resp.status_code == 200
    assert b"Inactive One" in resp.content
    assert b"Active One" not in resp.content


def test_search_applies(client):
    cookie = _login(client)
    _run(client, lambda: Author.create(name="Findme Unique", email="find@x.com"))
    resp = _auth_get(client, cookie, "/admin/author/?q=Findme")
    assert resp.status_code == 200
    assert b"Findme Unique" in resp.content


def test_bulk_delete(client):
    cookie = _login(client)
    a1 = _run(client, lambda: Author.create(name="Bulk1", email="b1@x.com"))
    a2 = _run(client, lambda: Author.create(name="Bulk2", email="b2@x.com"))
    resp = client.post(
        "/admin/author/bulk/",
        data=[
            ("action", "delete_selected"),
            ("bulk_ids", str(a1.id)),
            ("bulk_ids", str(a2.id)),
        ],
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert _run(client, lambda: Author.get_or_none(id=a1.id)) is None
    assert _run(client, lambda: Author.get_or_none(id=a2.id)) is None


def test_detail_reverse_relations(client):
    cookie = _login(client)
    author = _run(client, lambda: Author.create(name="Author With Books", email="awb@x.com"))
    _run(client, lambda: Book.create(title="Book A", author=author))
    _run(client, lambda: Book.create(title="Book B", author=author))
    resp = _auth_get(client, cookie, f"/admin/author/{author.id}/")
    assert resp.status_code == 200
    assert b"Book A" in resp.content
    assert b"Book B" in resp.content
    assert b"Related Objects" in resp.content


def test_activity_logged_on_create(client):
    cookie = _login(client)
    before = _run(client, lambda: AdminActivity.all().count())
    client.post(
        "/admin/author/create/",
        data={"name": "Logged User", "email": "lu@x.com", "is_active": "1"},
        follow_redirects=False,
    )
    after = _run(client, lambda: AdminActivity.all().count())
    assert after > before
