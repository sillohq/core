---
title: Declarations
description: Every screen is a frozen value — comparable, printable, generatable in a loop, and extendable with .with_().
---

Everything Warder draws is described by a value. Not a class body, not a
registry, not a decorator: an ordinary object you can name, store, compare,
print, generate in a loop and pass to a function.

```python
>>> from warder import Column, List
>>> screen = List(Column("title", link=True), per_page=50)
>>> screen
List(1 columns, 0 filters, 0 actions)
>>> screen.columns[0]
Column('title', link=True)
```

## Frozen

A declaration cannot be modified after it is built. Sequence and mapping
arguments are copied into read-only forms on the way in, so a `List` shared
between forty resources cannot be edited from a distance by the thirty-ninth.

```python
>>> screen.per_page = 100
AttributeError: List is a value and cannot be modified.
Use .with_(per_page=...) to build a new one.
```

## Extendable

`.with_()` returns a **new** declaration: positional parts appended, keywords
replaced.

```python
BASE = List(Column("id"), Column("name"), per_page=50)

admin.add(Resource(Tag,  list=BASE.with_(Column("slug"))))
admin.add(Resource(Team, list=BASE.with_(Column.relation("owner"))))
```

Appending rather than replacing is the deliberate choice: a shared base exists
to be added to, and a caller who wants to start over can build a new `List`.

An unrecognised keyword is refused, and the message says what is accepted:

```python
>>> screen.with_(per_pag=10)
TypeError: List.with_() got unexpected keyword 'per_pag'. Accepts: columns,
filters, actions, row_actions, sort, select_related, …
```

On the declarations that carry a `**options` catch-all — `Format`, `Widget`,
`Filter`, `Panel`, `Card`, `Outcome` — an unrecognised keyword is one of those
options instead:

```python
Format.badge().with_(default="red")
Filter.text("title").with_(lookup="istartswith")
```

## Generatable

Because a declaration is a value, generating forty of them is a function called
forty times.

```python
def reference(model, *names, icon="tag"):
    return Resource(
        model,
        group="Reference",
        icon=icon,
        list=List(
            *[Column(name, link=name == names[0]) for name in names],
            filters=[Filter.search(names[0])],
            sort=Sort.asc(names[0]),
        ),
        form=Form(Section("", *[Field(name) for name in names])),
    )

admin.add(reference(Department, "name", "code", icon="database"))
admin.add(reference(Tag, "name", "slug"))
```

## Nothing registers itself

A package ships declarations; the application decides whether to mount them.
Importing a module never changes what your admin contains.

```python
# billing/admin.py
resources = [Resource(Invoice, …), Resource(Payment, …)]

# app.py
from billing.admin import resources
admin.add(*resources)
```

That is the property a decorator-and-metaclass registry cannot have, and it is
why `admin.add` takes arguments rather than being a decorator.

## Where a declaration was written

Every declaration records the file and line it was built on, found by walking
out of Warder's own frames. It is what turns

```
Resource(Post).list column 'titel' is not a field of Post.
```

into an error you can act on without going looking for it:

```
  Did you mean 'title'?
  Declared at app/admin.py:24
```

```python
>>> Column("title").where
'app/admin.py:24'
```

## Two kinds of wrong, at two different times

A **wrong value** fails from the constructor, where the mistake was typed. It
needs nothing but the value to be judged:

```python
Column("total", align="middle")
# ValueError: align='middle' is not valid. Use one of: 'left', 'center', 'right'.
```

A **wrong reference** waits for `mount()`, because it cannot be judged without a
model:

```python
Column("titel")     # fine until the admin is mounted against Post
```

Keeping the first out of `mount()` matters: an error raised where the mistake
was typed is worth several raised somewhere else.
