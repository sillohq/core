"""sillo.admin.views — Template-based view handlers.

A Django-admin-level interface for sillo models:

* Password fields are auto-detected and rendered with a secure widget
  (reveal toggle + strength meter + confirmation). Plaintext is hashed on
  save via :func:`sillo.helpers.hashing.hash_password`.
* Many-to-many fields get a visual chip multi-select and are *actually*
  persisted through the relation manager.
* One-to-one / foreign-key fields get a searchable combobox.
* List views support search, column sorting, ``list_filter`` filtering,
  pagination, bulk actions, and per-row links.
* Detail views show reverse relations (inline "show related" panels).
* Every mutating action is permission-checked and audit-logged.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from tortoise import connections
from tortoise import fields as tf
from tortoise.expressions import Q
from tortoise.fields.relational import (
    BackwardFKRelation,
    BackwardOneToOneRelation,
    ForeignKeyFieldInstance,
    ManyToManyFieldInstance,
    OneToOneFieldInstance,
)

from sillo.helpers.hashing import hash_password
from sillo.pagination import AsyncDataHandler, AsyncPaginator, PageNumberPagination
from sillo.record.fields import PasswordField
from sillo.responses import html, redirect, text

from .models import AdminActivity
from .templating import render as _render

FKAliases = (ForeignKeyFieldInstance, OneToOneFieldInstance)
M2MAlias = ManyToManyFieldInstance


_HIDDEN_FIELDS = frozenset(
    {
        "id",
        "created_at",
        "updated_at",
        "deleted_at",
    }
)


def _should_skip_field(field_name: str) -> bool:
    """Should Skip Field"""
    return field_name in _HIDDEN_FIELDS or field_name.endswith("_id")


def _is_backward_relation(field_obj) -> bool:
    """Is Backward Relation"""
    return isinstance(field_obj, (BackwardFKRelation, BackwardOneToOneRelation))


def _is_password(field_obj, name: str = "") -> bool:
    """Is Password"""
    if isinstance(field_obj, PasswordField):
        return True
    if getattr(field_obj, "password", False):
        return True
    return bool(name and "password" in name.lower())


def _field_kind(field_obj, name: str = "") -> str:
    """Field Kind"""
    if _is_password(field_obj, name):
        return "password"
    if isinstance(field_obj, ManyToManyFieldInstance):
        return "m2m"
    if isinstance(field_obj, OneToOneFieldInstance):
        return "o2o"
    if isinstance(field_obj, ForeignKeyFieldInstance):
        return "fk"
    return "text"


def _related_model_name(field_obj) -> str:
    """Related Model Name"""
    parts = field_obj.model_name.split(".")
    return parts[-1] if parts else ""


async def _get_fk_options(field_obj, current_value=None):
    """Get Fk Options"""
    name = _related_model_name(field_obj)
    slug = name.lower()
    model = field_obj.related_model
    if model is None:
        return name, slug, []
    try:
        all_recs = await model.all()
    except Exception:
        return name, slug, []
    options = []
    for r in all_recs:
        pk = getattr(r, "pk", getattr(r, "id", None))
        label = str(r)
        selected = current_value is not None and str(pk) == str(current_value)
        options.append({"pk": pk, "label": label, "selected": selected})
    return name, slug, options


async def _get_m2m_options(field_obj, current_ids=None):
    """Get M2M Options"""
    name = _related_model_name(field_obj)
    slug = name.lower()
    model = field_obj.related_model
    if model is None:
        return name, slug, []
    try:
        all_recs = await model.all()
    except Exception:
        return name, slug, []
    current = {str(x) for x in (current_ids or [])}
    options = []
    for r in all_recs:
        pk = getattr(r, "pk", getattr(r, "id", None))
        options.append({"pk": pk, "label": str(r), "selected": str(pk) in current})
    return name, slug, options


def _find_forward_field(rel_model, target_model_cls):
    """Find the FK/O2O field on *rel_model* that points back at *target_model_cls*.

    Used to translate a backward relation (e.g. ``Supplier.products``) into
    the concrete field on the other side (``Product.supplier``) that has to
    be written to attach/detach a row.
    """
    for fn, fo in rel_model._meta.fields_map.items():
        if (
            isinstance(fo, (ForeignKeyFieldInstance, OneToOneFieldInstance))
            and getattr(fo, "related_model", None) is target_model_cls
        ):
            return fn, fo
    return None, None


def _field_widget(field_obj, name: str = "") -> str:
    """Field Widget"""
    kind = _field_kind(field_obj, name)
    if kind == "password":
        return "password"
    if kind in ("fk", "o2o", "m2m"):
        return "relation" if kind != "m2m" else "m2m"
    if isinstance(field_obj, tf.BooleanField):
        return "checkbox"
    if hasattr(field_obj, "field_type"):
        t = str(field_obj.field_type)
        if "int" in t or "float" in t or "decimal" in t:
            return "number"
        if "text" in t:
            return "textarea"
    if isinstance(field_obj, tf.TextField):
        return "textarea"
    return "input"


def _is_relation(field_obj) -> bool:
    """Is Relation"""
    return isinstance(field_obj, (FKAliases, M2MAlias))


def _field_label(field_name: str) -> str:
    """Field Label"""
    return field_name.replace("_", " ").title()


async def _resolve_fk_value(
    obj, field_name: str, field_obj, admin_site, *, as_link: bool = True
):
    """Resolve Fk Value"""
    try:
        related = await getattr(obj, field_name)
    except Exception:
        return "\u2014", None
    if related is None:
        return "\u2014", None
    related_pk = getattr(related, "pk", getattr(related, "id", None))
    label = str(related)
    if as_link and related_pk:
        related_slug = _related_model_name(field_obj).lower()
        link = f"{admin_site.prefix}/{related_slug}/{related_pk}/"
        return label, link
    return label, None


async def _resolve_m2m_value(obj, field_name: str, field_obj, admin_site):
    """Resolve M2M Value"""
    try:
        manager = getattr(obj, field_name)
        related = await manager.all()
    except Exception:
        return []
    results = []
    related_slug = _related_model_name(field_obj).lower()
    for r in related:
        pk = getattr(r, "pk", getattr(r, "id", None))
        label = str(r)
        link = f"{admin_site.prefix}/{related_slug}/{pk}/" if pk else None
        results.append((label, link))
    return results


async def _collect_form(request):
    """Collect Form"""
    form = await request.form

    def get(key):
        """Get"""
        v = form.get(key)
        return (
            v if isinstance(v, str) else (v[0] if isinstance(v, (list, tuple)) else v)
        )

    def getlist(key):
        """Getlist"""
        v = form.getlist(key)
        return [x for x in v if isinstance(x, str)]

    return get, getlist


# ── Shared helpers (ex-BaseView) ─────────────────────────────────────────


def model_links_html(site):
    """The sidebar entries: every registered model the database can serve.

    A model whose module the application never registered has no table, and its
    page would raise "default_connection cannot be None". The admin registers
    its own activity log without knowing whether the application wanted it, so
    that case is real — and a link the admin generated itself, leading to a 500,
    is worse than no link.

    This runs per request, which is the earliest the ORM can be asked.
    """
    links = []
    for m, admin_cls in site.registry:
        if not site._model_is_usable(m):
            continue
        name = getattr(admin_cls, "verbose_name", None) or m.__name__
        slug = m.__name__.lower()
        links.append({"name": name, "slug": slug})
    return links


def base_ctx(request, site, model_name="", model_slug=""):
    """Base Ctx"""
    return {
        "site_title": site.title,
        "site_prefix": site.prefix,
        "model_name": model_name,
        "model_slug": model_slug,
        "model_links": model_links_html(site),
        "user_email": (getattr(request, "session", {}) or {})
        .get("user", {})
        .get("display_name", "Admin"),
    }


def _forbidden(site_prefix):
    """Send someone without the permission back to the admin index."""
    return redirect(f"{site_prefix}/", status_code=302)


async def _current_admin_user(request, site):
    """Load the full logged-in user record for the current session.

    The session only stores ``{"id", "display_name"}``; this fetches the
    real row through ``site.auth.user_model`` for checks that need more
    than identity, e.g. ``is_superuser``.
    """
    session = getattr(request, "session", None)
    data = session.get("user") if session else None
    if not data:
        return None
    user_model = getattr(site.auth, "user_model", None)
    if user_model is None:
        return None
    try:
        return await user_model.load_user(data.get("id"))
    except Exception:
        return None


async def _log(request, action, model_name, site, object_id=None, detail=None):
    """Log"""
    try:
        ctx = base_ctx(request, site)
        await AdminActivity.create(
            user_email=ctx.get("user_email", "system"),
            action=action,
            model_name=model_name,
            object_id=str(object_id) if object_id is not None else None,
            detail=detail,
        )
    except Exception:
        pass


def _form_field_names(meta, admin, is_create):
    """Form Field Names"""
    raw = admin.get_fields(add=is_create)
    if raw:
        names = [f for f in raw if f in meta.fields_map]
    else:
        names = list(meta.fields_map.keys())
    exclude = list(admin.exclude or [])
    return [
        f
        for f in names
        if f not in exclude
        and not _should_skip_field(f)
        and not _is_backward_relation(meta.fields_map[f])
    ]


async def _build_form_fields(meta, admin, obj=None, is_create=True):
    """Build Form Fields"""
    is_update = not is_create
    names = _form_field_names(meta, admin, is_create)
    fields = []
    for f_name in names:
        field_obj = meta.fields_map[f_name]
        kind = _field_kind(field_obj, f_name)
        label = _field_label(f_name)
        readonly = (not is_create) and f_name in admin.readonly_fields
        required = not getattr(field_obj, "null", True)

        if kind == "password":
            fields.append(
                {
                    "widget": "password",
                    "name": f_name,
                    "label": label,
                    "value": "",
                    "required": required and is_create,
                    "readonly": readonly,
                    "help": "Leave blank to keep unchanged."
                    if is_update
                    else "Use a strong password (min 8 characters).",
                }
            )
            continue

        if isinstance(field_obj, FKAliases):
            rel_name, rel_slug, options = await _get_fk_options(
                field_obj,
                getattr(obj, f_name, None)
                and getattr(
                    getattr(obj, f_name),
                    "pk",
                    getattr(getattr(obj, f_name), "id", None),
                ),
            )
            fields.append(
                {
                    "widget": "relation",
                    "kind": kind,
                    "name": f_name,
                    "label": label,
                    "rel_name": rel_name,
                    "rel_slug": rel_slug,
                    "options": options,
                    "value": "",
                    "required": required,
                    "readonly": readonly,
                }
            )
            continue

        if isinstance(field_obj, M2MAlias):
            current_ids = None
            if obj is not None:
                try:
                    rels = await getattr(obj, f_name).all()
                    current_ids = [str(getattr(r, "pk", r.id)) for r in rels]
                except Exception:
                    current_ids = []
            rel_name, rel_slug, options = await _get_m2m_options(field_obj, current_ids)
            fields.append(
                {
                    "widget": "m2m",
                    "name": f_name,
                    "label": label,
                    "rel_name": rel_name,
                    "rel_slug": rel_slug,
                    "options": options,
                    "value": [],
                    "required": required,
                    "readonly": readonly,
                }
            )
            continue

        widget = _field_widget(field_obj, f_name)
        raw = getattr(obj, f_name, "") if obj is not None else ""
        fields.append(
            {
                "widget": widget,
                "name": f_name,
                "label": label,
                "value": str(raw) if raw is not None else "",
                "required": required,
                "readonly": readonly,
                "help": "",
            }
        )
    return fields


async def _fetch_reverse_related(obj, bf):
    """Fetch the rows attached to *obj* through a backward relation.

    Normalizes the two shapes Tortoise returns. A backward FK resolves to a
    list, but a backward one-to-one resolves to a single instance — or to
    ``None`` when nothing is linked yet, which raises no exception and so
    cannot be caught.

    Args:
        obj: The parent model instance.
        bf: The backward relation's field name.

    Returns:
        A list of related instances, empty when nothing is attached or the
        relation could not be read.
    """
    try:
        related = await getattr(obj, bf).all()
    except Exception:
        return []
    if related is None:
        return []
    if not isinstance(related, (list, tuple)):
        return [related]
    return related


async def _build_reverse_relation_fields(meta, model_cls, obj):
    """Build editable widgets for backward FK / O2O relations.

    Reuses the exact same "relation" (searchable combobox) and "m2m" (chip
    multi-select) widgets already used for forward FK/O2O/M2M fields, so the
    template needs no new markup. Field names are prefixed with ``rev__`` so
    :func:`_apply_reverse_relations` can tell them apart from the model's own
    columns on submit — see that function for the attach/detach semantics.

    Only meaningful once *obj* already exists, so this is only called from
    the update (edit) view, never create.
    """
    relations = []
    back_fk = list(getattr(meta, "backward_fk_fields", set()))
    back_o2o = list(getattr(meta, "backward_o2o_fields", set()))
    for bf in back_fk + back_o2o:
        field_obj = meta.fields_map.get(bf)
        rel_model = getattr(field_obj, "related_model", None)
        if rel_model is None:
            continue
        fwd, fwd_obj = _find_forward_field(rel_model, model_cls)
        if fwd is None:
            continue

        related = await _fetch_reverse_related(obj, bf)
        current_ids = {str(getattr(r, "pk", getattr(r, "id", None))) for r in related}

        try:
            all_recs = await rel_model.all()
        except Exception:
            all_recs = []
        options = [
            {
                "pk": getattr(r, "pk", getattr(r, "id", None)),
                "label": str(r),
                "selected": str(getattr(r, "pk", getattr(r, "id", None)))
                in current_ids,
            }
            for r in all_recs
        ]

        nullable = bool(getattr(fwd_obj, "null", False))
        label = f"{_field_label(bf)} ({rel_model.__name__})"
        help_text = (
            "Attach existing records; removing one unlinks it."
            if nullable
            else "Attach existing records. This relation is required on the "
            f"{rel_model.__name__} side, so removing one deletes it."
        )

        if bf in back_o2o:
            current_val = next(iter(current_ids), "")
            relations.append(
                {
                    "widget": "relation",
                    "kind": "o2o",
                    "name": f"rev__{bf}",
                    "label": label,
                    "rel_name": rel_model.__name__,
                    "options": options,
                    "value": current_val,
                    "required": False,
                    "readonly": False,
                    "help": help_text,
                }
            )
        else:
            relations.append(
                {
                    "widget": "m2m",
                    "name": f"rev__{bf}",
                    "label": label,
                    "rel_name": rel_model.__name__,
                    "options": options,
                    "value": [],
                    "required": False,
                    "readonly": False,
                    "help": help_text,
                }
            )
    return relations


async def _apply_reverse_relations(meta, model_cls, obj, get, getlist):
    """Persist edits made through :func:`_build_reverse_relation_fields`.

    For each backward FK/O2O relation, diffs the submitted set of related
    pks against the currently attached ones: newly-added pks get their
    forward FK pointed at *obj*; removed pks are unlinked (set to null) if
    the forward field allows it, otherwise the row is deleted outright since
    it cannot exist without a parent.
    """
    back_fk = list(getattr(meta, "backward_fk_fields", set()))
    back_o2o = list(getattr(meta, "backward_o2o_fields", set()))
    for bf in back_fk + back_o2o:
        field_obj = meta.fields_map.get(bf)
        rel_model = getattr(field_obj, "related_model", None)
        if rel_model is None:
            continue
        fwd, fwd_obj = _find_forward_field(rel_model, model_cls)
        if fwd is None:
            continue

        form_name = f"rev__{bf}"
        is_o2o = bf in back_o2o
        nullable = bool(getattr(fwd_obj, "null", False))

        current = await _fetch_reverse_related(obj, bf)
        current_ids = {str(getattr(r, "pk", getattr(r, "id", None))) for r in current}

        if is_o2o:
            raw = get(form_name)
            desired_ids = {raw} if raw else set()
        else:
            desired_ids = {x for x in getlist(form_name) if x}

        for pk in desired_ids - current_ids:
            child = await rel_model.get(pk=int(pk))
            setattr(child, f"{fwd}_id", obj.pk)
            await child.save()

        for pk in current_ids - desired_ids:
            child = await rel_model.get(pk=int(pk))
            if nullable:
                setattr(child, f"{fwd}_id", None)
                await child.save()
            else:
                await child.delete()


# ── Export helpers ───────────────────────────────────────────────────────

_EXPORT_ROW_CAP = 10000


def _csv_cell(v):
    """Coerce a raw cell value into something ``csv.writer`` can write safely."""
    if v is None:
        return ""
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray)):
        return v.hex()
    return str(v)


def _csv_export(columns, rows, filename):
    """Render *rows* (dicts) as a downloadable CSV attachment."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_csv_cell(row.get(c)) for c in columns])
    return text(
        buf.getvalue(),
        headers={
            "content-type": "text/csv; charset=utf-8",
            "content-disposition": f'attachment; filename="{filename}"',
        },
    )


def _json_export_default(value):
    """``json.dumps(default=...)`` handler for types SQL/ORM rows may contain."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return str(value)


def _json_export(rows, filename):
    """Render *rows* (dicts) as a downloadable JSON attachment."""
    body = json.dumps(list(rows), indent=2, default=_json_export_default)
    return text(
        body,
        headers={
            "content-type": "application/json; charset=utf-8",
            "content-disposition": f'attachment; filename="{filename}"',
        },
    )


# ── Route functions ──────────────────────────────────────────────────────


async def login_view(request, site):
    """Login View"""
    ctx = {
        "site_title": site.title,
        "site_prefix": site.prefix,
        "error": "",
    }
    if request.method == "POST":
        get, _ = await _collect_form(request)
        ok = await site.auth.login(request, get("email") or "", get("password") or "")
        if ok:
            try:
                user_model = getattr(site.auth, "user_model", None)
                await AdminActivity.create(
                    user_email=get("email") or "unknown",
                    action="login",
                    model_name=user_model.__name__ if user_model else "AdminUser",
                )
            except Exception:
                pass
            return redirect(f"{site.prefix}/", status_code=302)
        ctx["error"] = "Invalid credentials"
    return html(_render("login.html", **ctx))


async def logout_view(request, site):
    """Logout View"""
    await site.auth.logout(request)
    return redirect(f"{site.prefix}/login/", status_code=302)


async def dashboard_view(request, site):
    """Dashboard View"""
    ctx = base_ctx(request, site)
    ctx["title"] = "Dashboard"
    dashboard_models = []
    recent = []
    try:
        recent = await AdminActivity.all().order_by("-created_at").limit(10)
    except Exception:
        pass
    for m in site.registry.models:
        # Same reason the sidebar filters: a model the application never
        # registered has no table, and its card would link to a 500.
        if not site._model_is_usable(m):
            continue
        count = 0
        try:
            count = await m.all().count()
        except Exception:
            pass
        admin_cls = site.registry.get(m)
        can_add = False
        can_change = False
        can_delete = False
        try:
            can_add = bool(admin_cls.has_add_permission(request))
            can_change = bool(admin_cls.has_change_permission(request))
            can_delete = bool(admin_cls.has_delete_permission(request))
        except Exception:
            pass
        dashboard_models.append(
            {
                "name": getattr(admin_cls, "verbose_name", None) or m.__name__,
                "slug": m.__name__.lower(),
                "count": count,
                "can_add": can_add,
                "can_change": can_change,
                "can_delete": can_delete,
            }
        )
    ctx["dashboard_models"] = dashboard_models
    ctx["recent_activity"] = (
        [
            {
                "user_email": a.user_email,
                "action": a.action,
                "model_name": a.model_name,
                "created_at": str(a.created_at)[:19],
            }
            for a in recent
        ]
        if recent
        else []
    )
    return html(_render("dashboard.html", **ctx))


async def query_view(request, site):
    """Query View — run raw SQL against the app's database from the admin.

    Gated on ``is_superuser`` (rather than just "logged in") since it grants
    full read/write access to every table, not just the ones registered
    with the admin.
    """
    user = await _current_admin_user(request, site)
    if user is None or not getattr(user, "is_superuser", False):
        return _forbidden(site.prefix)

    tables = sorted(
        {
            (
                getattr(admin_cls, "verbose_name", None) or m.__name__,
                m._meta.db_table,
            )
            for m, admin_cls in site.registry
        },
        key=lambda t: t[0],
    )

    ctx = base_ctx(request, site, "Query", "query")
    ctx["title"] = "Query"
    ctx["tables"] = [{"name": n, "table": t} for n, t in tables]
    ctx["sql"] = ""
    ctx["error"] = ""
    ctx["columns"] = []
    ctx["rows"] = []
    ctx["rowcount"] = None

    if request.method == "POST":
        get, _ = await _collect_form(request)
        sql = (get("sql") or "").strip()
        export_fmt = get("export") or ""
        ctx["sql"] = sql
        if sql:
            try:
                conn = connections.get("default")
                rows, rowcount = await conn.execute_query_dict_with_affected(sql)
                ctx["rows"] = rows
                ctx["columns"] = list(rows[0].keys()) if rows else []
                ctx["rowcount"] = rowcount
                await _log(request, "query", "SQL", site, None, sql[:2000])
                if export_fmt in ("csv", "json"):
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                    if export_fmt == "json":
                        return _json_export(rows, f"query_{stamp}.json")
                    return _csv_export(
                        ctx["columns"], rows, f"query_{stamp}.csv"
                    )
            except Exception as e:
                ctx["error"] = str(e)

    return html(_render("query.html", **ctx))


async def export_view(request, site, model_cls, admin_cls):
    """Export View — download a model's (optionally filtered) list as CSV or JSON.

    Honors the same ``q`` (search) and ``f_<field>`` (list_filter) query
    params as :func:`list_view` so "export what I'm looking at" works, but
    ignores pagination and instead caps the result at ``_EXPORT_ROW_CAP``
    rows to avoid an unbounded dump.
    """
    if not admin_cls.has_view_permission(request):
        return _forbidden(site.prefix)

    model_name = getattr(admin_cls, "verbose_name", None) or model_cls.__name__
    model_slug = model_cls.__name__.lower()
    meta = model_cls._meta
    qs = model_cls.all()

    query = request.query_params.get("q", "")
    if query and admin_cls.search_fields:
        q_filter = Q()
        for f in admin_cls.search_fields:
            q_filter |= Q(**{f"{f}__icontains": query})
        qs = qs.filter(q_filter)

    for f in admin_cls.get_list_filter():
        if f not in meta.fields_map:
            continue
        val = request.query_params.get(f"f_{f}", "")
        if not val:
            continue
        fobj = meta.fields_map[f]
        ftype = _field_kind(fobj, f)
        if isinstance(fobj, tf.BooleanField):
            qs = qs.filter(**{f: val == "1"})
        elif ftype in ("fk", "o2o"):
            qs = qs.filter(**{f + "_id": int(val)})
        else:
            qs = qs.filter(**{f: val})

    sort = request.query_params.get("sort", "id")
    d = request.query_params.get("dir", "asc")
    dir_prefix = "-" if d == "desc" else ""
    try:
        qs = qs.order_by(f"{dir_prefix}{sort}")
    except Exception:
        pass

    items = await qs.limit(_EXPORT_ROW_CAP)

    columns = [c for c in admin_cls.list_display if not _should_skip_field(c)]
    column_info = []
    for col in columns:
        field_obj = meta.fields_map.get(col)
        kind = _field_kind(field_obj, col) if field_obj else "text"
        if kind == "password":
            continue
        column_info.append({"name": col, "type": kind, "field_obj": field_obj})

    out_rows = []
    for item in items:
        row = {}
        for ci in column_info:
            name = ci["name"]
            if ci["type"] in ("fk", "o2o") and ci["field_obj"]:
                label, _link = await _resolve_fk_value(
                    item, name, ci["field_obj"], site, as_link=False
                )
                row[name] = label
            elif ci["type"] == "m2m" and ci["field_obj"]:
                related = await _resolve_m2m_value(item, name, ci["field_obj"], site)
                row[name] = "; ".join(label for label, _link in related)
            else:
                row[name] = getattr(item, name, None)
        out_rows.append(row)

    out_columns = [ci["name"] for ci in column_info]
    fmt = (request.query_params.get("format") or "csv").lower()
    await _log(request, "export", model_name, site, None, f"{fmt}:{len(out_rows)} rows")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    if fmt == "json":
        return _json_export(out_rows, f"{model_slug}_{stamp}.json")
    return _csv_export(out_columns, out_rows, f"{model_slug}_{stamp}.csv")


async def list_view(request, site, model_cls, admin_cls):
    """List View"""
    if not admin_cls.has_view_permission(request):
        return _forbidden(site.prefix)

    model_name = getattr(admin_cls, "verbose_name", None) or model_cls.__name__
    model_slug = model_cls.__name__.lower()
    ctx = base_ctx(request, site, model_name, model_slug)
    ctx["title"] = model_name
    meta = model_cls._meta
    qs = model_cls.all()

    page = int(request.query_params.get("page", 1))
    page_size = admin_cls.list_per_page or 25
    sort = request.query_params.get("sort", "id")
    d = request.query_params.get("dir", "asc")
    query = request.query_params.get("q", "")

    if query and admin_cls.search_fields:
        q_filter = Q()
        for f in admin_cls.search_fields:
            q_filter |= Q(**{f"{f}__icontains": query})
        qs = qs.filter(q_filter)

    filters = []
    active_filters = {}
    for f in admin_cls.get_list_filter():
        if f not in meta.fields_map:
            continue
        fobj = meta.fields_map[f]
        ftype = _field_kind(fobj, f)
        param = f"f_{f}"
        val = request.query_params.get(param, "")
        spec = {
            "name": f,
            "param": param,
            "label": _field_label(f),
            "value": val,
            "type": "text",
            "options": [],
        }
        if isinstance(fobj, tf.BooleanField):
            spec["type"] = "bool"
            spec["options"] = [
                {"value": "1", "label": "Yes", "selected": val == "1"},
                {"value": "0", "label": "No", "selected": val == "0"},
            ]
        elif ftype in ("fk", "o2o"):
            _, _, opts = await _get_fk_options(fobj)
            spec["type"] = "relation"
            spec["options"] = [{"value": "", "label": "All", "selected": val == ""}] + [
                {
                    "value": str(o["pk"]),
                    "label": o["label"],
                    "selected": str(o["pk"]) == val,
                }
                for o in opts
            ]
        if val:
            active_filters[f] = val
        filters.append(spec)

    for f, val in active_filters.items():
        fobj = meta.fields_map[f]
        ftype = _field_kind(fobj, f)
        if isinstance(fobj, tf.BooleanField):
            qs = qs.filter(**{f: val == "1"})
        elif ftype in ("fk", "o2o"):
            qs = qs.filter(**{f + "_id": int(val)})
        else:
            qs = qs.filter(**{f: val})

    dir_prefix = "-" if d == "desc" else ""
    try:
        qs = qs.order_by(f"{dir_prefix}{sort}")
    except Exception:
        pass

    # Use Sillo's async pagination system
    class _QSAsyncDataHandler(AsyncDataHandler):
        def __init__(self, qs):
            self.qs = qs

        async def get_total_items(self) -> int:
            return await self.qs.count()

        async def get_items(self, offset: int, limit: int) -> list[Any]:
            return await self.qs.offset(offset).limit(limit)

    data_handler = _QSAsyncDataHandler(qs)
    # The strategy has its own default page size, so ``list_per_page`` has to be
    # handed to it explicitly or the admin's configured value never takes effect.
    strategy = PageNumberPagination(
        default_page_size=page_size,
        max_page_size=max(page_size, 100),
    )
    paginator = AsyncPaginator(
        data_handler=data_handler,
        pagination_strategy=strategy,
        base_url=str(request.url),
        request_params=dict(request.query_params),
        # A page past the end renders as empty rather than raising — rows get
        # deleted out from under bookmarked and back-button page links.
        validate_total_items=False,
    )
    paginated = await paginator.paginate()
    items = paginated["items"]
    pagination_meta = paginated["pagination"]
    total = pagination_meta["total_items"]
    page = pagination_meta["page"]
    page_size = pagination_meta["page_size"]
    total_pages = pagination_meta["total_pages"]
    page_range = (
        list(range(max(1, page - 2), min(total_pages, page + 2) + 1))
        if total_pages > 1
        else []
    )

    columns = [c for c in admin_cls.list_display if not _should_skip_field(c)]
    column_info = []
    for col in columns:
        field_obj = meta.fields_map.get(col)
        col_type = "text"
        if field_obj:
            kind = _field_kind(field_obj, col)
            if kind in ("fk", "o2o"):
                col_type = "fk"
            elif kind == "m2m":
                col_type = "m2m"
            elif kind == "password":
                col_type = "password"
        column_info.append({"name": col, "type": col_type, "field_obj": field_obj})

    rows = []
    for item in items:
        row_cells = []
        for ci in column_info:
            if ci["type"] == "fk" and ci["field_obj"]:
                label, link = await _resolve_fk_value(
                    item, ci["name"], ci["field_obj"], site
                )
                row_cells.append({"value": label, "link": link, "type": "fk"})
            elif ci["type"] == "m2m" and ci["field_obj"]:
                related = await _resolve_m2m_value(
                    item, ci["name"], ci["field_obj"], site
                )
                row_cells.append(
                    {
                        "value": f"{len(related)} item(s)",
                        "link": None,
                        "type": "m2m",
                        "items": related,
                    }
                )
            elif ci["type"] == "password":
                row_cells.append(
                    {
                        "value": "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022",
                        "link": None,
                        "type": "password",
                    }
                )
            else:
                raw = getattr(item, ci["name"], "")
                row_cells.append(
                    {
                        "value": "\u2014" if raw in (None, "") else str(raw),
                        "link": None,
                        "type": "text",
                    }
                )
        rows.append({"pk": item.pk, "cells": row_cells})

    link_cols = [
        c for c in (admin_cls.list_display_links or []) if not _should_skip_field(c)
    ]
    if not link_cols and columns:
        link_cols = [columns[0]]

    ctx.update(
        {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "sort": sort,
            "dir": d,
            "query": query,
            "columns": columns,
            "column_info": column_info,
            "link_cols": link_cols,
            "rows": rows,
            "filters": filters,
            "active_filter_count": len(active_filters),
            "bulk_actions": list(admin_cls.actions or []),
            "can_add": bool(admin_cls.has_add_permission(request)),
            "can_change": bool(admin_cls.has_change_permission(request)),
            "can_delete": bool(admin_cls.has_delete_permission(request)),
            "page_range": page_range,
        }
    )
    return html(_render("list.html", **ctx))


async def detail_view(request, site, model_cls, admin_cls, id):
    """Detail View"""
    if not admin_cls.has_view_permission(request):
        return _forbidden(site.prefix)

    model_name = getattr(admin_cls, "verbose_name", None) or model_cls.__name__
    model_slug = model_cls.__name__.lower()
    ctx = base_ctx(request, site, model_name, model_slug)
    try:
        obj = await model_cls.get(pk=id)
    except Exception:
        return text("Not Found", status_code=404)
    ctx["title"] = f"{model_name} #{id}"
    ctx["object_id"] = id
    ctx["can_change"] = bool(admin_cls.has_change_permission(request, obj))
    ctx["can_delete"] = bool(admin_cls.has_delete_permission(request, obj))

    meta = model_cls._meta
    fields = []
    # Show all model fields (except hidden/internal ones) on the detail view, ignoring any list_display restriction.
    # Backward relations (reverse FK/O2O) are rendered separately in the
    # "Related Objects" section below — including them here would stringify
    # the unawaited Tortoise relation manager (e.g. "<ReverseRelation object at ...>").
    display_cols = [
        c
        for c in meta.fields_map
        if not _should_skip_field(c) and not _is_backward_relation(meta.fields_map[c])
    ]
    for f in display_cols:
        label = _field_label(f)
        field_obj = meta.fields_map.get(f)
        kind = _field_kind(field_obj, f) if field_obj else "text"
        if kind == "password":
            fields.append(
                {
                    "label": label,
                    "value": "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022",
                    "type": "password",
                }
            )
        elif kind in ("fk", "o2o"):
            display, link = await _resolve_fk_value(obj, f, field_obj, site)
            fields.append(
                {"label": label, "value": display, "link": link, "type": "fk"}
            )
        elif kind == "m2m":
            related_list = await _resolve_m2m_value(obj, f, field_obj, site)
            fields.append({"label": label, "value": related_list, "type": "m2m"})
        else:
            fields.append(
                {
                    "label": label,
                    "value": str(getattr(obj, f, "")),
                    "link": None,
                    "type": "text",
                }
            )
    ctx["fields"] = fields

    reverse = []
    back_fields = (
        list(getattr(meta, "backward_fk_fields", set()))
        + list(getattr(meta, "backward_o2o_fields", set()))
        + list(getattr(meta, "m2m_fields", set()))
    )
    for bf in back_fields:
        try:
            field_obj = meta.fields_map[bf]
            rel_model = getattr(field_obj, "related_model", None)
            if rel_model is None:
                continue
            slug = rel_model.__name__.lower()
            manager = getattr(obj, bf)
            if hasattr(manager, "all"):
                related = await manager.all()
            else:
                related = list(manager) if manager else []
            fwd, _fwd_obj = _find_forward_field(rel_model, model_cls)
            list_link = (
                f"{site.prefix}/{slug}/?f_{fwd}={obj.pk}"
                if fwd
                else f"{site.prefix}/{slug}/"
            )
            items = [
                {
                    "label": str(r),
                    "link": f"{site.prefix}/{slug}/{getattr(r, 'pk', r.id)}/",
                }
                for r in related[:10]
            ]
            reverse.append(
                {
                    "label": _field_label(bf),
                    "model_name": rel_model.__name__,
                    "slug": slug,
                    "count": len(related),
                    "list_link": list_link,
                    "rows": items,
                }
            )
        except Exception:
            continue
    ctx["reverse_relations"] = reverse

    return html(_render("detail.html", **ctx))


async def create_view(request, site, model_cls, admin_cls):
    """Create View"""
    if not admin_cls.has_add_permission(request):
        return _forbidden(site.prefix)

    model_name = getattr(admin_cls, "verbose_name", None) or model_cls.__name__
    model_slug = model_cls.__name__.lower()
    ctx = base_ctx(request, site, model_name, model_slug)
    ctx["title"] = f"Add {model_name}"
    ctx["error"] = ""
    meta = model_cls._meta
    fields = await _build_form_fields(meta, admin_cls, is_create=True)
    ctx["fields"] = fields

    if request.method == "POST":
        get, getlist = await _collect_form(request)
        try:
            create_kwargs = {}
            m2m_data = {}
            for f_name in _form_field_names(meta, admin_cls, True):
                field_obj = meta.fields_map[f_name]
                kind = _field_kind(field_obj, f_name)
                if kind == "password":
                    pw = get(f_name) or ""
                    confirm = get(f_name + "__confirm") or ""
                    if not pw:
                        if not getattr(field_obj, "null", True):
                            raise ValueError(f"{_field_label(f_name)} is required")
                        continue
                    if pw != confirm:
                        raise ValueError("Passwords do not match")
                    if len(pw) < 8:
                        raise ValueError("Password must be at least 8 characters")
                    create_kwargs[f_name] = hash_password(pw)
                elif kind in ("fk", "o2o"):
                    v = get(f_name)
                    if v:
                        create_kwargs[f"{f_name}_id"] = int(v)
                    elif getattr(field_obj, "null", True):
                        create_kwargs[f"{f_name}_id"] = None
                elif kind == "m2m":
                    pks = [int(x) for x in getlist(f_name) if x]
                    m2m_data[f_name] = pks
                else:
                    if isinstance(field_obj, tf.BooleanField):
                        create_kwargs[f_name] = bool(get(f_name))
                    else:
                        v = get(f_name)
                        if v not in (None, ""):
                            create_kwargs[f_name] = v
                        elif getattr(field_obj, "null", True):
                            create_kwargs[f_name] = None
            obj = await model_cls.create(**create_kwargs)
            for name, pks in m2m_data.items():
                if not pks:
                    continue
                rel_model = meta.fields_map[name].related_model
                rels = [await rel_model.get(pk=pk) for pk in pks]
                await getattr(obj, name).add(*rels)
            await _log(request, "create", model_name, site, obj.pk)
            return redirect(
                f"{site.prefix}/{model_slug}/{obj.pk}/",
                status_code=302,
            )
        except Exception as e:
            ctx["error"] = str(e)
            for fld in fields:
                if fld["widget"] == "password":
                    fld["value"] = ""
                elif fld["widget"] in ("relation", "m2m"):
                    pass
                else:
                    fld["value"] = get(fld["name"]) or ""
    return html(_render("create.html", **ctx))


async def update_view(request, site, model_cls, admin_cls, id):
    """Update View"""
    if not admin_cls.has_change_permission(request):
        return _forbidden(site.prefix)

    model_name = getattr(admin_cls, "verbose_name", None) or model_cls.__name__
    model_slug = model_cls.__name__.lower()
    ctx = base_ctx(request, site, model_name, model_slug)
    ctx["error"] = ""
    try:
        obj = await model_cls.get(pk=id)
    except Exception:
        return text("Not Found", status_code=404)
    ctx["title"] = f"Edit {model_name} #{id}"
    ctx["object_id"] = id

    meta = model_cls._meta
    fields = await _build_form_fields(meta, admin_cls, obj=obj, is_create=False)
    ctx["fields"] = fields
    ctx["relation_fields"] = await _build_reverse_relation_fields(meta, model_cls, obj)

    if request.method == "POST":
        get, getlist = await _collect_form(request)
        try:
            for f_name in _form_field_names(meta, admin_cls, False):
                if f_name in admin_cls.readonly_fields:
                    continue
                field_obj = meta.fields_map[f_name]
                kind = _field_kind(field_obj, f_name)
                if kind == "password":
                    pw = get(f_name) or ""
                    if not pw:
                        continue
                    confirm = get(f_name + "__confirm") or ""
                    if pw != confirm:
                        raise ValueError("Passwords do not match")
                    if len(pw) < 8:
                        raise ValueError("Password must be at least 8 characters")
                    setattr(obj, f_name, hash_password(pw))
                elif kind in ("fk", "o2o"):
                    v = get(f_name)
                    setattr(obj, f"{f_name}_id", int(v) if v else None)
                elif kind == "m2m":
                    pks = [int(x) for x in getlist(f_name) if x]
                    rel_model = field_obj.related_model
                    rels = [await rel_model.get(pk=pk) for pk in pks]
                    mgr = getattr(obj, f_name)
                    await mgr.clear()
                    await mgr.add(*rels)
                else:
                    if isinstance(field_obj, tf.BooleanField):
                        setattr(obj, f_name, bool(get(f_name)))
                    else:
                        setattr(obj, f_name, get(f_name) or None)
            await obj.save()
            await _apply_reverse_relations(meta, model_cls, obj, get, getlist)
            await _log(request, "update", model_name, site, id)
            return redirect(
                f"{site.prefix}/{model_slug}/{id}/", status_code=302
            )
        except Exception as e:
            ctx["error"] = str(e)
            for fld in fields:
                if fld["widget"] == "password":
                    fld["value"] = ""
                elif fld["widget"] not in ("relation", "m2m"):
                    fld["value"] = get(fld["name"]) or ""
    return html(_render("update.html", **ctx))


async def delete_view(request, site, model_cls, admin_cls, id):
    """Delete View"""
    if not admin_cls.has_delete_permission(request):
        return _forbidden(site.prefix)

    model_name = getattr(admin_cls, "verbose_name", None) or model_cls.__name__
    model_slug = model_cls.__name__.lower()
    ctx = base_ctx(request, site, model_name, model_slug)
    try:
        obj = await model_cls.get(pk=id)
    except Exception:
        return text("Not Found", status_code=404)
    ctx["title"] = f"Delete {model_name} #{id}"
    ctx["object_id"] = id
    if request.method == "POST":
        await _log(request, "delete", model_name, site, id)
        await obj.delete()
        return redirect(f"{site.prefix}/{model_slug}/", status_code=302)
    return html(_render("delete.html", **ctx))


async def bulk_view(request, site, model_cls, admin_cls):
    """Bulk View"""
    model_name = getattr(admin_cls, "verbose_name", None) or model_cls.__name__
    model_slug = model_cls.__name__.lower()
    if request.method != "POST":
        return redirect(f"{site.prefix}/{model_slug}/", status_code=302)
    if not admin_cls.has_delete_permission(request):
        return _forbidden(site.prefix)
    get, getlist = await _collect_form(request)
    action = get("action") or ""
    ids = [int(x) for x in getlist("bulk_ids") if x]
    if action == "delete_selected" and ids:
        await model_cls.filter(pk__in=ids).delete()
        await _log(request, "delete", model_name, site, None, f"bulk:{ids}")
    return redirect(f"{site.prefix}/{model_slug}/", status_code=302)
