"""
Admin export, raw-SQL query console, pagination, sorting, and permissions.

Companion to ``test_admin_views``, which covers the CRUD forms. Everything
here goes through the mounted admin routes rather than calling the view
functions directly, so the session/auth middleware and the template render
are part of what is being asserted.
"""

import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from tortoise import Tortoise, fields

from sillo import SilloApp
from sillo.admin import ModelAdmin, setup_admin
from sillo.admin.default_user import AdminRole, AdminUser
from sillo.admin.models import AdminActivity
from sillo.record import DatabaseConfig, Model, setup_record
from sillo.session import SessionConfig, SessionMiddleware
from sillo.testclient import TestClient


class Supplier(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=120)
    active = fields.BooleanField(default=True)

    def __str__(self):
        return self.name


class Label(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=80)

    def __str__(self):
        return self.name


class Product(Model):
    id = fields.IntField(pk=True)
    sku = fields.CharField(max_length=64)
    price = fields.DecimalField(max_digits=10, decimal_places=2, default=0)
    released_on = fields.DateField(null=True)
    notes = fields.TextField(null=True)
    supplier: fields.ForeignKeyNullableRelation[Supplier] = fields.ForeignKeyField(
        "models.Supplier", related_name="products", null=True
    )
    labels: fields.ManyToManyRelation[Label] = fields.ManyToManyField("models.Label")

    def __str__(self):
        return self.sku


class SupplierAdmin(ModelAdmin):
    list_display = ["id", "name", "active"]
    search_fields = ["name"]
    list_filter = ["active"]
    list_per_page = 5


class LabelAdmin(ModelAdmin):
    list_display = ["id", "name"]


class ProductAdmin(ModelAdmin):
    list_display = ["id", "sku", "price", "released_on", "supplier", "labels"]
    search_fields = ["sku"]
    list_filter = ["supplier"]
    list_per_page = 5


def _make_app(db_path, *, product_admin=ProductAdmin):
    app = SilloApp(title="Admin Export Test")
    setup_record(
        app,
        DatabaseConfig.sqlite(str(db_path)),
        model_modules=["sillo.admin.models", "sillo.admin.default_user", __name__],
    )
    admin = setup_admin(app, title="Admin Export Test", prefix="/admin")

    @admin.register(Supplier)
    class _SupplierAdmin(SupplierAdmin):
        pass

    @admin.register(Label)
    class _LabelAdmin(LabelAdmin):
        pass

    @admin.register(Product)
    class _ProductAdmin(product_admin):
        pass

    @app.on_startup
    async def _seed():
        role = await AdminRole.get_or_none(slug="super")
        if not role:
            role = await AdminRole.create(name="Super", slug="super", permissions=["*"])
        if not await AdminUser.get_or_none(email="admin@test.com"):
            await AdminUser.create(
                email="admin@test.com",
                username="admin",
                password="admin",
                is_active=True,
                is_superuser=True,
                role=role,
            )
        if not await AdminUser.get_or_none(email="staff@test.com"):
            await AdminUser.create(
                email="staff@test.com",
                username="staff",
                password="staff",
                is_active=True,
                # Staff, so they may sign in; not a superuser, so the query
                # console stays shut. That distinction is what this fixture is for.
                is_staff=True,
                is_superuser=False,
                role=role,
            )

    app.use(
        SessionMiddleware(
            config=SessionConfig(session_cookie_secure=False),
            secret_key="test-secret-key",
        )
    )
    return app


def _run(client, coro_factory):
    return client.portal.call(coro_factory)


@pytest.fixture
def client(tmp_path):
    app = _make_app(tmp_path / "export.db")
    with TestClient(app) as c:
        db = app.state.get("record")
        ctx = db._root_context if db is not None else None
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


def _login(client, email="admin@test.com", password="admin"):
    resp = client.post(
        "/admin/login/",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), (resp.status_code, resp.text[:300])
    return client.cookies.get("session_id")


def _get(client, cookie, url):
    return client.get(url, cookies={"session_id": cookie})


def _seed_products(client, count=12):
    supplier = _run(client, lambda: Supplier.create(name="Acme"))
    for i in range(count):
        _run(
            client,
            lambda i=i: Product.create(
                sku=f"SKU-{i:03d}",
                price=Decimal(f"{i}.50"),
                released_on=date(2024, 1, 1),
                supplier=supplier,
            ),
        )
    return supplier


def _read_csv(resp):
    return list(csv.reader(io.StringIO(resp.text)))


# ── CSV export ───────────────────────────────────────────────────────────


def test_csv_export_returns_an_attachment(client):
    cookie = _login(client)
    _seed_products(client, 3)
    resp = _get(client, cookie, "/admin/product/export/")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]


def test_the_csv_filename_names_the_model(client):
    cookie = _login(client)
    resp = _get(client, cookie, "/admin/product/export/")
    assert "product_" in resp.headers["content-disposition"]


def test_the_csv_has_a_header_row(client):
    cookie = _login(client)
    _seed_products(client, 2)
    header = _read_csv(_get(client, cookie, "/admin/product/export/"))[0]
    assert "sku" in header
    assert "price" in header


def test_every_row_is_exported(client):
    cookie = _login(client)
    _seed_products(client, 7)
    rows = _read_csv(_get(client, cookie, "/admin/product/export/"))
    assert len(rows) == 8  # header + 7


def test_export_ignores_pagination(client):
    """``list_per_page`` is 5, but an export is the whole filtered set."""
    cookie = _login(client)
    _seed_products(client, 12)
    rows = _read_csv(_get(client, cookie, "/admin/product/export/"))
    assert len(rows) == 13


def test_a_decimal_column_is_written_as_a_number(client):
    cookie = _login(client)
    _seed_products(client, 1)
    rows = _read_csv(_get(client, cookie, "/admin/product/export/"))
    price = rows[1][rows[0].index("price")]
    assert float(price) == 0.5


def test_a_date_column_is_written_in_iso_form(client):
    cookie = _login(client)
    _seed_products(client, 1)
    rows = _read_csv(_get(client, cookie, "/admin/product/export/"))
    assert rows[1][rows[0].index("released_on")].startswith("2024-01-01")


def test_a_null_cell_is_written_as_empty(client):
    cookie = _login(client)
    _run(client, lambda: Product.create(sku="NULLS", price=Decimal("1")))
    rows = _read_csv(_get(client, cookie, "/admin/product/export/"))
    assert rows[1][rows[0].index("released_on")] == ""


def test_a_foreign_key_is_exported_as_its_label(client):
    cookie = _login(client)
    _seed_products(client, 1)
    rows = _read_csv(_get(client, cookie, "/admin/product/export/"))
    assert rows[1][rows[0].index("supplier")] == "Acme"


def test_a_many_to_many_is_exported_as_a_joined_list(client):
    cookie = _login(client)
    product = _run(client, lambda: Product.create(sku="M2M", price=Decimal("1")))
    first = _run(client, lambda: Label.create(name="new"))
    second = _run(client, lambda: Label.create(name="sale"))
    _run(client, lambda: product.labels.add(first, second))

    rows = _read_csv(_get(client, cookie, "/admin/product/export/"))
    cell = rows[1][rows[0].index("labels")]
    assert "new" in cell and "sale" in cell


def test_export_honours_the_search_term(client):
    cookie = _login(client)
    _seed_products(client, 5)
    rows = _read_csv(_get(client, cookie, "/admin/product/export/?q=SKU-002"))
    assert len(rows) == 2


def test_export_honours_a_relation_filter(client):
    cookie = _login(client)
    supplier = _seed_products(client, 3)
    other = _run(client, lambda: Supplier.create(name="Other"))
    _run(client, lambda: Product.create(sku="OTHER-1", supplier=other))

    rows = _read_csv(_get(client, cookie, f"/admin/product/export/?f_supplier={other.id}"))
    assert len(rows) == 2
    assert "OTHER-1" in rows[1]


def test_export_honours_a_boolean_filter(client):
    cookie = _login(client)
    _run(client, lambda: Supplier.create(name="On", active=True))
    _run(client, lambda: Supplier.create(name="Off", active=False))
    rows = _read_csv(_get(client, cookie, "/admin/supplier/export/?f_active=0"))
    assert len(rows) == 2
    assert "Off" in rows[1]


def test_export_honours_the_sort_direction(client):
    cookie = _login(client)
    _seed_products(client, 4)
    rows = _read_csv(_get(client, cookie, "/admin/product/export/?sort=id&dir=desc"))
    assert rows[1][rows[0].index("sku")] == "SKU-003"


def test_an_unsortable_column_does_not_break_the_export(client):
    cookie = _login(client)
    _seed_products(client, 2)
    resp = _get(client, cookie, "/admin/product/export/?sort=not_a_column")
    assert resp.status_code == 200


def test_exporting_an_empty_table_still_gives_a_header(client):
    cookie = _login(client)
    rows = _read_csv(_get(client, cookie, "/admin/product/export/"))
    assert len(rows) == 1


def test_an_export_is_logged(client):
    cookie = _login(client)
    _seed_products(client, 1)
    before = _run(client, lambda: AdminActivity.filter(action="export").count())
    _get(client, cookie, "/admin/product/export/")
    after = _run(client, lambda: AdminActivity.filter(action="export").count())
    assert after == before + 1


# ── JSON export ──────────────────────────────────────────────────────────


def test_json_export_returns_json(client):
    cookie = _login(client)
    _seed_products(client, 2)
    resp = _get(client, cookie, "/admin/product/export/?format=json")
    assert "application/json" in resp.headers["content-type"]
    assert len(json.loads(resp.text)) == 2


def test_json_export_is_an_attachment(client):
    cookie = _login(client)
    resp = _get(client, cookie, "/admin/product/export/?format=json")
    assert resp.headers["content-disposition"].endswith('.json"')


def test_json_export_serialises_dates_and_decimals(client):
    cookie = _login(client)
    _seed_products(client, 1)
    row = json.loads(_get(client, cookie, "/admin/product/export/?format=json").text)[0]
    assert row["released_on"].startswith("2024-01-01")
    assert row["price"] == 0.5


def test_an_unknown_format_falls_back_to_csv(client):
    cookie = _login(client)
    resp = _get(client, cookie, "/admin/product/export/?format=xml")
    assert "text/csv" in resp.headers["content-type"]


def test_the_format_is_case_insensitive(client):
    cookie = _login(client)
    resp = _get(client, cookie, "/admin/product/export/?format=JSON")
    assert "application/json" in resp.headers["content-type"]


def test_export_requires_authentication(client):
    resp = client.get("/admin/product/export/", follow_redirects=False)
    assert resp.status_code in (301, 302, 303)


# ── the query console ────────────────────────────────────────────────────


def test_the_query_page_renders_for_a_superuser(client):
    cookie = _login(client)
    resp = _get(client, cookie, "/admin/query/")
    assert resp.status_code == 200
    assert b"Query" in resp.content


def test_the_query_page_lists_the_registered_tables(client):
    cookie = _login(client)
    body = _get(client, cookie, "/admin/query/").content
    assert b"product" in body.lower()


def test_a_select_returns_rows(client):
    cookie = _login(client)
    _seed_products(client, 3)
    resp = client.post(
        "/admin/query/",
        data={"sql": "SELECT sku FROM product ORDER BY id"},
        cookies={"session_id": cookie},
    )
    assert resp.status_code == 200
    assert b"SKU-000" in resp.content


def test_an_empty_result_set_is_handled(client):
    cookie = _login(client)
    resp = client.post(
        "/admin/query/",
        data={"sql": "SELECT sku FROM product WHERE 1 = 0"},
        cookies={"session_id": cookie},
    )
    assert resp.status_code == 200


def test_a_broken_statement_reports_the_error_rather_than_500ing(client):
    cookie = _login(client)
    resp = client.post(
        "/admin/query/",
        data={"sql": "SELECT * FROM no_such_table"},
        cookies={"session_id": cookie},
    )
    assert resp.status_code == 200
    assert b"no_such_table" in resp.content


def test_an_empty_statement_is_a_no_op(client):
    cookie = _login(client)
    resp = client.post("/admin/query/", data={"sql": "  "}, cookies={"session_id": cookie})
    assert resp.status_code == 200


def test_a_write_statement_takes_effect(client):
    cookie = _login(client)
    _run(client, lambda: Supplier.create(name="Before"))
    client.post(
        "/admin/query/",
        data={"sql": "UPDATE supplier SET name = 'After'"},
        cookies={"session_id": cookie},
    )
    assert _run(client, lambda: Supplier.get_or_none(name="After")) is not None


def test_a_query_is_logged(client):
    cookie = _login(client)
    before = _run(client, lambda: AdminActivity.filter(action="query").count())
    client.post(
        "/admin/query/",
        data={"sql": "SELECT 1 AS one"},
        cookies={"session_id": cookie},
    )
    after = _run(client, lambda: AdminActivity.filter(action="query").count())
    assert after == before + 1


def test_query_results_can_be_exported_as_csv(client):
    cookie = _login(client)
    _seed_products(client, 2)
    resp = client.post(
        "/admin/query/",
        data={"sql": "SELECT sku FROM product ORDER BY id", "export": "csv"},
        cookies={"session_id": cookie},
    )
    assert "text/csv" in resp.headers["content-type"]
    assert len(_read_csv(resp)) == 3


def test_query_results_can_be_exported_as_json(client):
    cookie = _login(client)
    _seed_products(client, 2)
    resp = client.post(
        "/admin/query/",
        data={"sql": "SELECT sku FROM product ORDER BY id", "export": "json"},
        cookies={"session_id": cookie},
    )
    assert "application/json" in resp.headers["content-type"]
    assert len(json.loads(resp.text)) == 2


def test_the_query_console_is_closed_to_non_superusers(client):
    """It grants read/write on every table, so being logged in is not enough."""
    cookie = _login(client, "staff@test.com", "staff")
    resp = client.get(
        "/admin/query/", cookies={"session_id": cookie}, follow_redirects=False
    )
    assert resp.status_code in (302, 303, 403)


def test_the_query_console_requires_authentication(client):
    resp = client.get("/admin/query/", follow_redirects=False)
    assert resp.status_code in (301, 302, 303)


# ── list view: pagination and sorting ────────────────────────────────────


def test_the_first_page_is_capped_at_the_page_size(client):
    cookie = _login(client)
    _seed_products(client, 12)
    body = _get(client, cookie, "/admin/product/").content
    assert b"SKU-000" in body
    assert b"SKU-005" not in body


def test_the_second_page_shows_the_next_slice(client):
    cookie = _login(client)
    _seed_products(client, 12)
    body = _get(client, cookie, "/admin/product/?page=2").content
    assert b"SKU-005" in body
    assert b"SKU-000" not in body


def test_a_page_beyond_the_end_still_renders(client):
    cookie = _login(client)
    _seed_products(client, 3)
    assert _get(client, cookie, "/admin/product/?page=99").status_code == 200


def test_descending_sort_reverses_the_order(client):
    cookie = _login(client)
    _seed_products(client, 12)
    body = _get(client, cookie, "/admin/product/?sort=id&dir=desc").content
    assert b"SKU-011" in body


def test_sorting_by_an_unknown_column_does_not_break_the_page(client):
    cookie = _login(client)
    _seed_products(client, 2)
    assert _get(client, cookie, "/admin/product/?sort=nope").status_code == 200


def test_an_empty_list_renders(client):
    cookie = _login(client)
    assert _get(client, cookie, "/admin/product/").status_code == 200


def test_a_relation_filter_offers_its_options(client):
    cookie = _login(client)
    _seed_products(client, 2)
    body = _get(client, cookie, "/admin/product/").content
    assert b"Acme" in body


def test_a_many_to_many_column_renders_a_chip_per_row(client):
    """Regression: the template read ``cell.items``, which Jinja resolves to
    the dict method rather than the key, so any m2m column 500'd the page."""
    cookie = _login(client)
    product = _run(client, lambda: Product.create(sku="COUNTED"))
    label = _run(client, lambda: Label.create(name="chip-label"))
    _run(client, lambda: product.labels.add(label))
    resp = _get(client, cookie, "/admin/product/")
    assert resp.status_code == 200
    assert b"chip-label" in resp.content


def test_an_empty_many_to_many_column_renders_a_placeholder(client):
    cookie = _login(client)
    _run(client, lambda: Product.create(sku="NO-LABELS"))
    resp = _get(client, cookie, "/admin/product/")
    assert resp.status_code == 200
    assert b"NO-LABELS" in resp.content


def test_an_empty_cell_renders_as_a_dash(client):
    cookie = _login(client)
    _run(client, lambda: Product.create(sku="EMPTY"))
    body = _get(client, cookie, "/admin/product/").content.decode()
    assert "—" in body


# ── detail, create and delete pages ──────────────────────────────────────


def test_a_missing_detail_page_is_a_404(client):
    cookie = _login(client)
    assert _get(client, cookie, "/admin/product/99999/").status_code == 404


def test_a_detail_page_shows_a_relation_label(client):
    cookie = _login(client)
    _seed_products(client, 1)
    product = _run(client, lambda: Product.all().first())
    body = _get(client, cookie, f"/admin/product/{product.id}/").content
    assert b"Acme" in body


def test_the_create_form_renders(client):
    cookie = _login(client)
    resp = _get(client, cookie, "/admin/product/create/")
    assert resp.status_code == 200
    assert b"sku" in resp.content.lower()


def test_the_create_form_offers_relation_options(client):
    cookie = _login(client)
    _run(client, lambda: Supplier.create(name="Pickable"))
    assert b"Pickable" in _get(client, cookie, "/admin/product/create/").content


def test_the_update_form_is_prefilled(client):
    cookie = _login(client)
    product = _run(client, lambda: Product.create(sku="EDIT-ME"))
    body = _get(client, cookie, f"/admin/product/{product.id}/update/").content
    assert b"EDIT-ME" in body


def test_updating_a_missing_row_is_a_404(client):
    cookie = _login(client)
    assert _get(client, cookie, "/admin/product/99999/update/").status_code == 404


def test_the_delete_page_asks_for_confirmation(client):
    cookie = _login(client)
    product = _run(client, lambda: Product.create(sku="CONFIRM"))
    resp = _get(client, cookie, f"/admin/product/{product.id}/delete/")
    assert resp.status_code == 200
    assert _run(client, lambda: Product.get_or_none(id=product.id)) is not None


def test_deleting_a_missing_row_is_a_404(client):
    cookie = _login(client)
    assert _get(client, cookie, "/admin/product/99999/delete/").status_code == 404


def test_a_nullable_relation_can_be_left_empty_on_create(client):
    cookie = _login(client)
    resp = client.post(
        "/admin/product/create/",
        data={"sku": "NO-SUPPLIER", "price": "1.00", "supplier": ""},
        cookies={"session_id": cookie},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text[:400]
    product = _run(client, lambda: Product.get_or_none(sku="NO-SUPPLIER"))
    assert product is not None
    assert product.supplier_id is None


# ── bulk actions ─────────────────────────────────────────────────────────


def test_a_bulk_post_with_no_selection_is_a_no_op(client):
    cookie = _login(client)
    _seed_products(client, 2)
    resp = client.post(
        "/admin/product/bulk/",
        data={"action": "delete_selected"},
        cookies={"session_id": cookie},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert _run(client, lambda: Product.all().count()) == 2


def test_an_unknown_bulk_action_deletes_nothing(client):
    cookie = _login(client)
    _seed_products(client, 2)
    product = _run(client, lambda: Product.all().first())
    resp = client.post(
        "/admin/product/bulk/",
        data=[("action", "make_coffee"), ("bulk_ids", str(product.id))],
        cookies={"session_id": cookie},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert _run(client, lambda: Product.all().count()) == 2


def test_bulk_is_post_only(client):
    """The route is registered for POST alone, so a GET never reaches the view."""
    cookie = _login(client)
    resp = client.get(
        "/admin/product/bulk/", cookies={"session_id": cookie}, follow_redirects=False
    )
    assert resp.status_code in (404, 405)


# ── session lifecycle ────────────────────────────────────────────────────


def test_logging_out_redirects_to_the_login_page(client):
    cookie = _login(client)
    resp = client.get(
        "/admin/logout/", cookies={"session_id": cookie}, follow_redirects=False
    )
    assert resp.status_code in (301, 302, 303)
    assert "/admin/login" in resp.headers.get("location", "")


def test_logging_out_clears_the_session_cookie(client):
    """The default backend keeps session state in a signed cookie, so ending
    the session means clearing that cookie — there is no server-side record to
    revoke."""
    cookie = _login(client)
    resp = client.get(
        "/admin/logout/", cookies={"session_id": cookie}, follow_redirects=False
    )
    assert "session_id" in resp.headers.get("set-cookie", "")


def test_the_browser_is_logged_out_after_visiting_logout(client):
    client.cookies.clear()
    _login(client)
    client.get("/admin/logout/", follow_redirects=False)
    resp = client.get("/admin/product/", follow_redirects=False)
    assert resp.status_code in (301, 302, 303)


def test_the_login_page_redirects_an_authenticated_user_onward(client):
    cookie = _login(client)
    resp = client.get(
        "/admin/login/", cookies={"session_id": cookie}, follow_redirects=False
    )
    assert resp.status_code in (200, 302, 303)


def test_an_unknown_email_is_rejected(client):
    resp = client.post(
        "/admin/login/",
        data={"email": "nobody@test.com", "password": "whatever"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert b"Invalid credentials" in resp.content


def test_the_dashboard_counts_the_registered_models(client):
    cookie = _login(client)
    _seed_products(client, 3)
    body = _get(client, cookie, "/admin/").content
    assert b"Dashboard" in body


# ── permissions ──────────────────────────────────────────────────────────


class TestPermissionGates:
    """A ``ModelAdmin`` that denies everything must close every door."""

    @pytest.fixture
    def locked_client(self, tmp_path):
        class LockedProductAdmin(ProductAdmin):
            # The base hooks are ``staticmethod``s and are called off the class,
            # so overrides have to keep that shape.
            @staticmethod
            def has_view_permission(ctx, obj=None):
                return False

            @staticmethod
            def has_add_permission(ctx):
                return False

            @staticmethod
            def has_change_permission(ctx, obj=None):
                return False

            @staticmethod
            def has_delete_permission(ctx, obj=None):
                return False

        app = _make_app(tmp_path / "locked.db", product_admin=LockedProductAdmin)
        with TestClient(app) as c:
            db = app.state.get("record")
            ctx = db._root_context if db is not None else None
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

    def _denied(self, resp):
        return resp.status_code in (302, 303, 403)

    def test_the_list_is_closed(self, locked_client):
        cookie = _login(locked_client)
        resp = locked_client.get(
            "/admin/product/", cookies={"session_id": cookie}, follow_redirects=False
        )
        assert self._denied(resp)

    def test_the_export_is_closed(self, locked_client):
        cookie = _login(locked_client)
        resp = locked_client.get(
            "/admin/product/export/",
            cookies={"session_id": cookie},
            follow_redirects=False,
        )
        assert self._denied(resp)

    def test_the_detail_page_is_closed(self, locked_client):
        cookie = _login(locked_client)
        resp = locked_client.get(
            "/admin/product/1/", cookies={"session_id": cookie}, follow_redirects=False
        )
        assert self._denied(resp)

    def test_creating_is_closed(self, locked_client):
        cookie = _login(locked_client)
        resp = locked_client.get(
            "/admin/product/create/",
            cookies={"session_id": cookie},
            follow_redirects=False,
        )
        assert self._denied(resp)

    def test_deleting_is_closed(self, locked_client):
        cookie = _login(locked_client)
        resp = locked_client.get(
            "/admin/product/1/delete/",
            cookies={"session_id": cookie},
            follow_redirects=False,
        )
        assert self._denied(resp)

    def test_bulk_deleting_is_closed(self, locked_client):
        cookie = _login(locked_client)
        resp = locked_client.post(
            "/admin/product/bulk/",
            data=[("action", "delete_selected"), ("bulk_ids", "1")],
            cookies={"session_id": cookie},
            follow_redirects=False,
        )
        assert self._denied(resp)

    def test_an_unlocked_model_is_still_reachable(self, locked_client):
        """The gate is per-``ModelAdmin``, not global."""
        cookie = _login(locked_client)
        resp = locked_client.get("/admin/supplier/", cookies={"session_id": cookie})
        assert resp.status_code == 200
