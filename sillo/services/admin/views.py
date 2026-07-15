"""sillo.services.admin.views — Template-based view handlers."""

from __future__ import annotations
from sillo.services.admin.models import AdminActivity

import math

from tortoise.fields.relational import (
    ForeignKeyFieldInstance,
    OneToOneFieldInstance,
    ManyToManyFieldInstance,
)
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
    return field_name in _HIDDEN_FIELDS or field_name.endswith("_id")


def _field_kind(field_obj) -> str:
    if isinstance(field_obj, ManyToManyFieldInstance):
        return "m2m"
    if isinstance(field_obj, OneToOneFieldInstance):
        return "o2o"
    if isinstance(field_obj, ForeignKeyFieldInstance):
        return "fk"
    return "text"


def _related_model_name(field_obj) -> str:
    """Extract 'AdminRole' from 'models.AdminRole'."""
    parts = field_obj.model_name.split(".")
    return parts[-1] if parts else ""


async def _get_fk_options(field_obj, current_value=None):
    """Query all records of the related model for a <select> dropdown."""
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
    """Multi-select options for M2M."""
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


def _field_type_class(field_obj) -> str:
    """Infer HTML input type."""
    if hasattr(field_obj, "field_type"):
        if field_obj.field_type is not None:
            t = str(field_obj.field_type)
            if "bool" in t:
                return "checkbox"
            if "int" in t or "float" in t or "decimal" in t:
                return "number"
            if "text" in t:
                return "textarea"
    return "text"


def _is_relation(field_obj) -> bool:
    return isinstance(field_obj, FKAliases) or isinstance(field_obj, M2MAlias)


def _field_label(field_name: str) -> str:
    return field_name.replace("_", " ").title()


async def _resolve_fk_value(
    obj, field_name: str, field_obj, admin_site, *, as_link: bool = True
):
    """Return (display_text, link_url_or_None)."""
    try:
        related = await getattr(obj, field_name)
    except Exception:
        return "—", None
    if related is None:
        return "—", None
    related_pk = getattr(related, "pk", getattr(related, "id", None))
    label = str(related)
    if as_link and related_pk:
        related_slug = _related_model_name(field_obj).lower()
        link = f"{admin_site.prefix}/{related_slug}/{related_pk}/"
        return label, link
    return label, None


async def _resolve_m2m_value(obj, field_name: str, field_obj, admin_site):
    """Return list of (label, link_or_None) tuples."""
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


class BaseView:
    def __init__(self, site, model_class=None, admin_class=None):
        self.site = site
        self.model_class = model_class
        self.admin_class = admin_class
        self.model_name = model_class.__name__ if model_class else ""
        self.model_slug = self.model_name.lower()
        self._model_links_cache = None

    def model_links_html(self):
        if self._model_links_cache:
            return self._model_links_cache
        links = []
        for m in self.site.registry.models:
            name = m.__name__
            slug = name.lower()
            links.append({"name": name, "slug": slug})
        self._model_links_cache = links
        return links

    def base_ctx(self, request):
        return {
            "site_title": self.site.title,
            "site_prefix": self.site.prefix,
            "model_name": self.model_name,
            "model_slug": self.model_slug,
            "model_links": self.model_links_html(),
            "user_email": getattr(request, "session", {})
            .get("admin_user", {})
            .get("email", "Admin"),
            "has_admin_users": True,
            "has_roles": True,
        }


class DashboardView(BaseView):
    async def handle(self, request, response):
        ctx = self.base_ctx(request)
        ctx["title"] = "Dashboard"
        dashboard_models = []
        recent = []
        try:
            recent = await AdminActivity.all().order_by("-created_at").limit(10)
        except Exception:
            pass
        for m in self.site.registry.models:
            count = 0
            try:
                count = await m.all().count()
            except Exception:
                pass
            dashboard_models.append(
                {"name": m.__name__, "slug": m.__name__.lower(), "count": count}
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


class ListView(BaseView):
    async def handle(self, request, response):
        ctx = self.base_ctx(request)
        ctx["title"] = self.model_name
        admin = self.admin_class
        qs = self.model_class.all()

        page = int(request.query_params.get("page", 1))
        page_size = 25
        sort = request.query_params.get("sort", "id")
        d = request.query_params.get("dir", "asc")
        query = request.query_params.get("q", "")

        if query and admin.search_fields:
            from tortoise.expressions import Q

            q_filter = Q()
            for f in admin.search_fields:
                q_filter |= Q(**{f"{f}__icontains": query})
            qs = qs.filter(q_filter)

        dir_prefix = "-" if d == "desc" else ""
        try:
            qs = qs.order_by(f"{dir_prefix}{sort}")
        except Exception:
            pass

        total = await qs.count()
        total_pages = max(1, math.ceil(total / page_size))
        offset = (page - 1) * page_size
        items = await qs.offset(offset).limit(page_size)

        columns = [c for c in admin.list_display if not _should_skip_field(c)]

        meta = self.model_class._meta
        column_info = []
        for col in columns:
            field_obj = meta.fields_map.get(col) if meta else None
            col_type = "text"
            if field_obj:
                kind = _field_kind(field_obj)
                if kind == "fk":
                    col_type = "fk"
                elif kind == "o2o":
                    col_type = "fk"
                elif kind == "m2m":
                    col_type = "m2m"
            column_info.append({"name": col, "type": col_type, "field_obj": field_obj})

        rows = []
        for item in items:
            row_cells = []
            for ci in column_info:
                raw = ""
                if ci["type"] == "fk" and ci["field_obj"]:
                    label, link = await _resolve_fk_value(
                        item, ci["name"], ci["field_obj"], self.site
                    )
                    raw = {"label": label, "link": link}
                elif ci["type"] == "m2m" and ci["field_obj"]:
                    related = await _resolve_m2m_value(
                        item, ci["name"], ci["field_obj"], self.site
                    )
                    raw = {"label": f"{len(related)} items", "link": None}
                else:
                    raw = str(getattr(item, ci["name"], ""))
                row_cells.append(raw)
            rows.append({"pk": item.pk, "cells": row_cells})

        ctx.update(
            {
                "total": total,
                "page": page,
                "total_pages": total_pages,
                "sort": sort,
                "dir": d,
                "query": query,
                "columns": columns,
                "column_info": column_info,
                "rows": rows,
                "page_range": list(
                    range(max(1, page - 2), min(total_pages, page + 2) + 1)
                )
                if total_pages > 1
                else [],
            }
        )
        return response.html(_render("list.html", **ctx))


class DetailView(BaseView):
    async def handle(self, request, response, id):
        ctx = self.base_ctx(request)
        try:
            obj = await self.model_class.get(pk=id)
        except Exception:
            return response.text("Not Found", status_code=404)
        ctx["title"] = f"{self.model_name} #{id}"
        ctx["object_id"] = id

        meta = self.model_class._meta if hasattr(self.model_class, "_meta") else None
        fields = []
        display_cols = [
            c for c in self.admin_class.list_display if not _should_skip_field(c)
        ]
        for f in display_cols:
            label = _field_label(f)
            field_obj = meta.fields_map.get(f) if meta else None
            kind = _field_kind(field_obj) if field_obj else "text"
            if kind in ("fk", "o2o"):
                display, link = await _resolve_fk_value(obj, f, field_obj, self.site)
                fields.append(
                    {"label": label, "value": display, "link": link, "type": "fk"}
                )
            elif kind == "m2m":
                related_list = await _resolve_m2m_value(obj, f, field_obj, self.site)
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
        return response.html(_render("detail.html", **ctx))


class CreateView(BaseView):
    async def handle(self, request, response):
        ctx = self.base_ctx(request)
        ctx["title"] = f"Add {self.model_name}"
        ctx["error"] = ""
        meta = self.model_class._meta if hasattr(self.model_class, "_meta") else None
        fields = []
        if meta:
            for f_name in meta.fields_map:
                if _should_skip_field(f_name):
                    continue
                field_obj = meta.fields_map[f_name]
                if _is_relation(field_obj):
                    fields.append(await self._build_rel_field(field_obj, f_name, None))
                else:
                    ftype = _field_type_class(field_obj)
                    fields.append(
                        {
                            "name": f_name,
                            "label": _field_label(f_name),
                            "type": ftype,
                            "value": "",
                            "kind": "scalar",
                            "required": not getattr(field_obj, "null", True),
                            "help": "",
                        }
                    )
        ctx["fields"] = fields

        if request.method == "POST":
            data = dict(await request.form)
            try:
                create_kwargs = await self._prepare_rel_data(data, meta)
                obj = await self.model_class.create(**create_kwargs)
                return response.redirect(
                    f"{self.site.prefix}/{self.model_slug}/{obj.pk}/", status_code=302
                )
            except Exception as e:
                ctx["error"] = str(e)
                for fld in fields:
                    fld["value"] = data.get(fld["name"], "")
        return response.html(_render("create.html", **ctx))

    async def _build_rel_field(self, field_obj, f_name, current_value):
        kind = _field_kind(field_obj)
        label = _field_label(f_name)
        if kind in ("fk", "o2o"):
            rel_name, rel_slug, options = await _get_fk_options(
                field_obj, current_value
            )
            return {
                "name": f_name,
                "label": label,
                "kind": kind,
                "rel_name": rel_name,
                "rel_slug": rel_slug,
                "options": options,
                "value": str(current_value or ""),
                "required": not getattr(field_obj, "null", True),
            }
        if kind == "m2m":
            rel_name, rel_slug, options = await _get_m2m_options(
                field_obj, current_value
            )
            return {
                "name": f_name,
                "label": label,
                "kind": "m2m",
                "rel_name": rel_name,
                "rel_slug": rel_slug,
                "options": options,
                "value": [],
            }
        return None

    async def _prepare_rel_data(self, data, meta):
        """Convert form data to Tortoise-compatible kwargs."""
        create_kwargs = {}
        for k, v in data.items():
            if k not in meta.fields_map:
                continue
            field_obj = meta.fields_map[k]
            kind = _field_kind(field_obj)
            if kind in ("fk", "o2o"):
                if v:
                    create_kwargs[f"{k}_id"] = int(v)
                elif getattr(field_obj, "null", True):
                    create_kwargs[f"{k}_id"] = None
            elif kind == "m2m":
                pass
            else:
                create_kwargs[k] = v
        return create_kwargs


class UpdateView(BaseView):
    async def handle(self, request, response, id):
        ctx = self.base_ctx(request)
        ctx["error"] = ""
        try:
            obj = await self.model_class.get(pk=id)
        except Exception:
            return response.text("Not Found", status_code=404)
        ctx["title"] = f"Edit {self.model_name} #{id}"
        ctx["object_id"] = id

        meta = self.model_class._meta if hasattr(self.model_class, "_meta") else None
        fields = []
        if meta:
            for f_name in meta.fields_map:
                if _should_skip_field(f_name):
                    continue
                field_obj = meta.fields_map[f_name]
                is_readonly = f_name in self.admin_class.readonly_fields
                if _is_relation(field_obj):
                    kind = _field_kind(field_obj)
                    current = getattr(obj, f_name, None)
                    current_pk = (
                        getattr(current, "pk", getattr(current, "id", None))
                        if current and not isinstance(current, (list, type(None)))
                        else None
                    )
                    fld = await self._build_rel_field(field_obj, f_name, current_pk)
                    if fld:
                        fld["readonly"] = is_readonly
                        fields.append(fld)
                else:
                    ftype = _field_type_class(field_obj)
                    raw = getattr(obj, f_name, "")
                    fields.append(
                        {
                            "name": f_name,
                            "label": _field_label(f_name),
                            "type": ftype,
                            "value": str(raw) if raw is not None else "",
                            "kind": "scalar",
                            "readonly": is_readonly,
                            "required": not getattr(field_obj, "null", True),
                        }
                    )
        ctx["fields"] = fields

        if request.method == "POST":
            data = dict(await request.form)
            try:
                for k, v in data.items():
                    if (
                        k not in meta.fields_map
                        or k in self.admin_class.readonly_fields
                    ):
                        continue
                    field_obj = meta.fields_map[k]
                    kind = _field_kind(field_obj)
                    if kind in ("fk", "o2o"):
                        setattr(obj, f"{k}_id", int(v) if v else None)
                    elif kind == "m2m":
                        pass
                    else:
                        setattr(obj, k, v)
                await obj.save()
                return response.redirect(
                    f"{self.site.prefix}/{self.model_slug}/{id}/", status_code=302
                )
            except Exception as e:
                ctx["error"] = str(e)
                for fld in fields:
                    fld["value"] = data.get(fld["name"], fld.get("value", ""))
        return response.html(_render("update.html", **ctx))

    async def _build_rel_field(self, field_obj, f_name, current_value):
        kind = _field_kind(field_obj)
        label = _field_label(f_name)
        if kind in ("fk", "o2o"):
            rel_name, rel_slug, options = await _get_fk_options(
                field_obj, current_value
            )
            return {
                "name": f_name,
                "label": label,
                "kind": kind,
                "rel_name": rel_name,
                "rel_slug": rel_slug,
                "options": options,
                "value": str(current_value or ""),
                "required": not getattr(field_obj, "null", True),
            }
        if kind == "m2m":
            current_ids = None
            try:
                rel_name, rel_slug, options = await _get_m2m_options(
                    field_obj, current_ids
                )
                return {
                    "name": f_name,
                    "label": label,
                    "kind": "m2m",
                    "rel_name": rel_name,
                    "rel_slug": rel_slug,
                    "options": options,
                    "value": [],
                }
            except Exception:
                pass
        return None


class DeleteView(BaseView):
    async def handle(self, request, response, id):
        ctx = self.base_ctx(request)
        try:
            obj = await self.model_class.get(pk=id)
        except Exception:
            return response.text("Not Found", status_code=404)
        ctx["title"] = f"Delete {self.model_name} #{id}"
        ctx["object_id"] = id
        if request.method == "POST":
            await obj.delete()
            return response.redirect(
                f"{self.site.prefix}/{self.model_slug}/", status_code=302
            )
        return response.html(_render("delete.html", **ctx))


class LoginView(BaseView):
    async def handle(self, request, response):
        ctx = {
            "site_title": self.site.title,
            "site_prefix": self.site.prefix,
            "error": "",
        }
        if request.method == "POST":
            data = dict(await request.form)
            ok = await self.site.auth.login(
                request, data.get("email", ""), data.get("password", "")
            )
            if ok:
                return response.redirect(f"{self.site.prefix}/", status_code=302)
            ctx["error"] = "Invalid credentials"
        return response.html(_render("login.html", **ctx))
