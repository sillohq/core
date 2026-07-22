"""sillo.services.admin.views — Template-based view handlers.

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

import math

from tortoise import fields as tf
from tortoise.expressions import Q
from tortoise.fields.relational import (
    BackwardFKRelation,
    BackwardOneToOneRelation,
    ForeignKeyFieldInstance,
    ManyToManyFieldInstance,
    OneToOneFieldInstance,
)
from sillo.record.fields import PasswordField
from sillo.helpers.hashing import hash_password, verify_password
from .templating import render as _render
from .models import AdminActivity

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
    return field_name in _HIDDEN_FIELDS or field_name.endswith("_id")


def _is_backward_relation(field_obj) -> bool:
    return isinstance(field_obj, (BackwardFKRelation, BackwardOneToOneRelation))


def _is_password(field_obj, name: str = "") -> bool:
    if isinstance(field_obj, PasswordField):
        return True
    if getattr(field_obj, "password", False):
        return True
    if name and "password" in name.lower():
        return True
    return False


def _field_kind(field_obj, name: str = "") -> str:
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
    parts = field_obj.model_name.split(".")
    return parts[-1] if parts else ""


async def _get_fk_options(field_obj, current_value=None):
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
    name = _related_model_name(field_obj)
    slug = name.lower()
    model = field_obj.related_model
    if model is None:
        return name, slug, []
    try:
        all_recs = await model.all()
    except Exception:
        return name, slug, []
    current = set(str(x) for x in (current_ids or []))
    options = []
    for r in all_recs:
        pk = getattr(r, "pk", getattr(r, "id", None))
        options.append({"pk": pk, "label": str(r), "selected": str(pk) in current})
    return name, slug, options


def _field_widget(field_obj, name: str = "") -> str:
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
    return isinstance(field_obj, FKAliases) or isinstance(field_obj, M2MAlias)


def _field_label(field_name: str) -> str:
    return field_name.replace("_", " ").title()


async def _resolve_fk_value(
    obj, field_name: str, field_obj, admin_site, *, as_link: bool = True
):
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
    form = await request.form

    def get(key):
        v = form.get(key)
        return (
            v if isinstance(v, str) else (v[0] if isinstance(v, (list, tuple)) else v)
        )

    def getlist(key):
        v = form.getlist(key)
        return [x for x in v if isinstance(x, str)]

    return get, getlist


# ── Shared helpers (ex-BaseView) ─────────────────────────────────────────


def model_links_html(site):
    links = []
    for m in site.registry.models:
        name = m.__name__
        slug = name.lower()
        links.append({"name": name, "slug": slug})
    return links


def base_ctx(request, site, model_name="", model_slug=""):
    return {
        "site_title": site.title,
        "site_prefix": site.prefix,
        "model_name": model_name,
        "model_slug": model_slug,
        "model_links": model_links_html(site),
        "user_email": getattr(request, "session", {})
        .get("admin_user", {})
        .get("email", "Admin"),
        "has_admin_users": True,
        "has_roles": True,
    }


def _forbidden(response, site_prefix):
    return response.redirect(f"{site_prefix}/", status_code=302)


async def _log(request, action, model_name, site, object_id=None, detail=None):
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
                    current_ids = [
                        str(getattr(r, "pk", getattr(r, "id"))) for r in rels
                    ]
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


# ── Route functions ──────────────────────────────────────────────────────


async def login_view(request, response, site):
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
                await AdminActivity.create(
                    user_email=get("email") or "unknown",
                    action="login",
                    model_name="AdminUser",
                )
            except Exception:
                pass
            return response.redirect(f"{site.prefix}/", status_code=302)
        ctx["error"] = "Invalid credentials"
    return response.html(_render("login.html", **ctx))


async def logout_view(request, response, site):
    await site.auth.logout(request)
    return response.redirect(f"{site.prefix}/login/", status_code=302)


async def dashboard_view(request, response, site):
    ctx = base_ctx(request, site)
    ctx["title"] = "Dashboard"
    dashboard_models = []
    recent = []
    try:
        recent = await AdminActivity.all().order_by("-created_at").limit(10)
    except Exception:
        pass
    for m in site.registry.models:
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
                "name": m.__name__,
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
    return response.html(_render("dashboard.html", **ctx))


async def list_view(request, response, site, model_cls, admin_cls):
    if not admin_cls.has_view_permission(request):
        return _forbidden(response, site.prefix)

    model_name = model_cls.__name__
    model_slug = model_name.lower()
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

    total = await qs.count()
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    items = await qs.offset(offset).limit(page_size)

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
            "page_range": (
                list(range(max(1, page - 2), min(total_pages, page + 2) + 1))
                if total_pages > 1
                else []
            ),
        }
    )
    return response.html(_render("list.html", **ctx))


async def detail_view(request, response, site, model_cls, admin_cls, id):
    if not admin_cls.has_view_permission(request):
        return _forbidden(response, site.prefix)

    model_name = model_cls.__name__
    model_slug = model_name.lower()
    ctx = base_ctx(request, site, model_name, model_slug)
    try:
        obj = await model_cls.get(pk=id)
    except Exception:
        return response.text("Not Found", status_code=404)
    ctx["title"] = f"{model_name} #{id}"
    ctx["object_id"] = id
    ctx["can_change"] = bool(admin_cls.has_change_permission(request, obj))
    ctx["can_delete"] = bool(admin_cls.has_delete_permission(request, obj))

    meta = model_cls._meta
    fields = []
    display_cols = [c for c in admin_cls.list_display if not _should_skip_field(c)]
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
            fwd = None
            for fn, fo in rel_model._meta.fields_map.items():
                if (
                    isinstance(fo, (ForeignKeyFieldInstance, OneToOneFieldInstance))
                    and getattr(fo, "related_model", None) is model_cls
                ):
                    fwd = fn
                    break
            list_link = (
                f"{site.prefix}/{slug}/?f_{fwd}={obj.pk}"
                if fwd
                else f"{site.prefix}/{slug}/"
            )
            items = [
                {
                    "label": str(r),
                    "link": f"{site.prefix}/{slug}/{getattr(r, 'pk', getattr(r, 'id'))}/",
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

    return response.html(_render("detail.html", **ctx))


async def create_view(request, response, site, model_cls, admin_cls):
    if not admin_cls.has_add_permission(request):
        return _forbidden(response, site.prefix)

    model_name = model_cls.__name__
    model_slug = model_name.lower()
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
            return response.redirect(
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
    return response.html(_render("create.html", **ctx))


async def update_view(request, response, site, model_cls, admin_cls, id):
    if not admin_cls.has_change_permission(request):
        return _forbidden(response, site.prefix)

    model_name = model_cls.__name__
    model_slug = model_name.lower()
    ctx = base_ctx(request, site, model_name, model_slug)
    ctx["error"] = ""
    try:
        obj = await model_cls.get(pk=id)
    except Exception:
        return response.text("Not Found", status_code=404)
    ctx["title"] = f"Edit {model_name} #{id}"
    ctx["object_id"] = id

    meta = model_cls._meta
    fields = await _build_form_fields(meta, admin_cls, obj=obj, is_create=False)
    ctx["fields"] = fields

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
            await _log(request, "update", model_name, site, id)
            return response.redirect(
                f"{site.prefix}/{model_slug}/{id}/", status_code=302
            )
        except Exception as e:
            ctx["error"] = str(e)
            for fld in fields:
                if fld["widget"] == "password":
                    fld["value"] = ""
                elif fld["widget"] not in ("relation", "m2m"):
                    fld["value"] = get(fld["name"]) or ""
    return response.html(_render("update.html", **ctx))


async def delete_view(request, response, site, model_cls, admin_cls, id):
    if not admin_cls.has_delete_permission(request):
        return _forbidden(response, site.prefix)

    model_name = model_cls.__name__
    model_slug = model_name.lower()
    ctx = base_ctx(request, site, model_name, model_slug)
    try:
        obj = await model_cls.get(pk=id)
    except Exception:
        return response.text("Not Found", status_code=404)
    ctx["title"] = f"Delete {model_name} #{id}"
    ctx["object_id"] = id
    if request.method == "POST":
        await _log(request, "delete", model_name, site, id)
        await obj.delete()
        return response.redirect(f"{site.prefix}/{model_slug}/", status_code=302)
    return response.html(_render("delete.html", **ctx))


async def bulk_view(request, response, site, model_cls, admin_cls):
    model_name = model_cls.__name__
    model_slug = model_name.lower()
    if request.method != "POST":
        return response.redirect(f"{site.prefix}/{model_slug}/", status_code=302)
    if not admin_cls.has_delete_permission(request):
        return _forbidden(response, site.prefix)
    get, getlist = await _collect_form(request)
    action = get("action") or ""
    ids = [int(x) for x in getlist("bulk_ids") if x]
    if action == "delete_selected" and ids:
        await model_cls.filter(pk__in=ids).delete()
        await _log(request, "delete", model_name, site, None, f"bulk:{ids}")
    return response.redirect(f"{site.prefix}/{model_slug}/", status_code=302)
