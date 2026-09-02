---
title: API reference
description: Every name Warder exports, and what it is for.
---

Everything below is importable from `warder`.

## The site

| | |
|---|---|
| `Admin(title=, prefix=, auth=, theme=, groups=, brand=, logo=, favicon=, footer=, secret=, sessions=, wide=, name=)` | One admin site |
| `admin.add(*items)` | Register resources, pages, cards and a dashboard. Chains |
| `admin.roles(*roles)` | Declare roles |
| `admin.slot(name, component)` | Mount your own component into a named region |
| `admin.check()` | Everything wrong that needs no ORM. Returns a list |
| `admin.bind()` | Resolve every resource against its model. Raises on the first problem |
| `admin.mount(app)` | Check, bind, then register routes |
| `admin.render(ctx, list, rows)` | Draw a `List` in your own route |
| `admin.navigation(allowed=)` | The sidebar, as groups of links |
| `admin.permissions` | Every permission this site declares |
| `admin.resource_for(model)` / `admin.at(slug)` | Look-ups |

## Resources and screens

| | |
|---|---|
| `Resource(model, *, label=, plural=, icon=, group=, slug=, stem=, list=, form=, detail=, access=, scope=, queryset=, search=, sort=, actions=, creatable=, editable=, deletable=, hidden=, weight=, description=)` | One model's surface |
| `crud(model, *fields, group=, stem=, **options)` | A resource over those fields |
| `List(*columns, filters=, actions=, row_actions=, sort=, select_related=, prefetch_related=, per_page=, per_page_options=, empty=, selectable=, sticky_header=, density=, totals=, group_by=, export=, limit=, description=)` | A table |
| `Form(*parts, submit=, layout=, sidebar=, on_save=, validate=, deletable=, cancel=, width=, description=)` | The add and edit screen |
| `Detail(*panels, actions=, title=, subtitle=, layout=, description=)` | One row, in full |
| `Section(title, *fields, description=, collapsed=, columns=, show=, access=, icon=)` | A group of inputs |
| `Empty(title, description=, action=, icon=)` | What a list shows when there is nothing |

### List properties

`joins` · `prefetches` · `column_map` · `filter_map` · `action_map` · `search` ·
`link_column` · `sorted_by(sort)`

## Columns

`Column(name, *, label=, format=, link=, sort=, align=, width=, access=, help=,
derive=, display=, related=, multiple=, hidden=, wrap=, empty=, sticky=,
toggle=)`

**Shorthands** — `text` · `code` · `number` · `money` · `percent` · `bytes` ·
`duration` · `date` · `boolean` · `badge` · `tags` · `progress` · `image` ·
`avatar` · `json` · `relation` · `many` · `compute` · `url`

**Properties** — `key` · `heading` · `computed` · `traversal` · `relation_path` ·
`sortable` · `sort_field` · `alignment`

## Formats and widgets

`Format(kind, **options)` — `text` `code` `markdown` `html` `number` `money`
`percent` `bytes` `duration` `date` `relative` `boolean` `badge` `tags`
`progress` `rating` `color` `link` `image` `avatar` `json`

`Widget(kind, **options)` — `text` `textarea` `markdown` `rich` `code`
`password` `slug` `email` `url` `phone` `number` `money` `range` `select`
`radio` `checkbox` `switch` `tags` `date` `datetime` `time` `duration` `file`
`image` `json` `keyvalue` `color` `relation` `hidden`

## Fields and filters

`Field(name, *, label=, widget=, help=, placeholder=, required=, editable=,
default=, access=, hidden=, span=, show=, validate=, autofocus=, unit=)`

**Shorthands** — `readonly` · `text` · `textarea` · `markdown` · `rich` · `code`
· `password` · `slug` · `email` · `url` · `phone` · `number` · `money` ·
`range` · `select` · `radio` · `switch` · `tags` · `date` · `datetime` · `time`
· `duration` · `color` · `file` · `image` · `json` · `keyvalue` · `relation`

`Filter` — `search` · `text` · `choice` · `boolean` · `exists` · `date_range` ·
`number_range` · `relation` · `toggle` · `custom`

## Actions and outcomes

`Action(label, run, *, name=, icon=, confirm=, access=, gate=, style=,
selection=, place=, fields=, description=, keyboard=, options=)` ·
`Action.delete()` · `Action.export()` · `Action.link()`

`notice` · `warning` · `problem` · `go` · `download` · `modal` · `refresh` ·
`nothing` → `Outcome`

## Panels, pages and cards

`Panel.fields` · `Panel.inline` · `Panel.related` · `Panel.custom` · `Panel.text`

`Page(path, title, render, *, icon=, group=, gate=, component=, name=, weight=,
description=, hidden=)`

`Card.number` · `Card.chart` · `Card.table` · `Card.custom` ·
`Dashboard(*cards, title=, columns=, description=)`

## Permissions

| | |
|---|---|
| `Gate` | `always` `never` `staff` `superuser` `permission` `role` `custom` `any` `all`, and `\|` `&` `~` |
| `Access(view=, add=, change=, delete=)` | plus `open` `readonly` `none` `by_permission` |
| `Scope` | `all` `none` `by` `query` `owner` `tenant` |
| `Role(name, *, grants=, inherits=, label=, description=)` | plus `Role.crud(*models)` |
| `current_user(ctx)` | The signed-in account, or `None`. Use this, not `ctx.user` |

## Authentication

`Auth(users=, backend=, gate=, permissions=, session=, login=, mfa=,
impersonation=, audit=, roles=)`

`Session(idle=, absolute=, concurrent=, revoke_on_password_change=, cookie=,
secure=, same_site=, visible=)`

`Login(throttle=, remember=, providers=, redirect=, message=, field=, lockout=,
password_reset=)`

`MFA.totp()` · `MFA.webauthn()` · `Impersonation(...)` · `Audit(retain=,
redact=, actions=, diff=)`

> `MFA` and `Impersonation` are declarable but not yet enforced.

## Sorting, conditions and theme

`Sort.asc` · `Sort.desc` · `Sort.by` · `Sort.none` · `.then()` · `.reversed()` ·
`.as_terms()`

`When(field, equals=|not_equals=|any_of=|none_of=|is_true=|is_false=|empty=)` ·
`When.all` · `When.any` · `~`

`Theme(style, *, accent=, radius=, density=, font=, mono=, logo=, favicon=,
dark=, tokens=, wide=)` · `Theme.console()` `paper()` `grid()` `native()`

## Errors

| | |
|---|---|
| `WarderError` | Base for everything |
| `DeclarationError` | A declaration is wrong. Raised at mount, with the line |
| `Denied` | This person may not do this. Expected, not a bug |
| `ActionFailed` | An action stopped itself with a message |
| `NotConfigured` | Something was used before what it needs was set up |

## Introspection

`Schema.of(model)` · `.fields` · `.editable` · `.relations` · `.shadows` ·
`.resolve(path)` — what Warder reads from a model, in its own terms.

`warder.resolve` — `bind(resource)` · `check(resource)` · `derive_list` ·
`derive_form` · `derive_detail` · `dress` · `dress_list` · `widget_for` ·
`format_for` · `display_for`
