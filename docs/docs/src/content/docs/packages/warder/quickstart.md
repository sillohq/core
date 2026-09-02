---
title: Quickstart
description: A working admin in one file — models, a resource, an account to sign in with, and the screens you get for free.
---

Five minutes, one file, and a running admin.

## Install

```bash
pip install "sillo-framework @ git+https://github.com/sillohq/core@main"
pip install warder --no-deps
```

Sillo v1 is not on PyPI yet, so the framework comes from git and Warder is
installed without re-resolving it. Once v1 ships this is one `pip install`.

## One file

```python
from tortoise import Tortoise, fields

from sillo import SilloApp
from sillo.record import DatabaseConfig, Model, setup_record
from sillo.users import User
from warder import Admin, Auth, Column, Gate, List, Resource, Sort

app = SilloApp()


class Student(Model):
    admission_no = fields.CharField(max_length=20, unique=True)
    first_name = fields.CharField(max_length=60)
    last_name = fields.CharField(max_length=60)
    status = fields.CharField(max_length=20, default="enrolled")
    admitted = fields.DateField(null=True)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"

    class Meta:
        table = "students"


admin = Admin(title="Ridgeway College", prefix="/admin", auth=Auth(users=User))
admin.add(Resource(Student))

db = setup_record(
    app,
    DatabaseConfig.sqlite("school.db"),
    model_modules=["app", "sillo.users.base"],
)
Tortoise.init_models(["app", "sillo.users.base"], "models")
admin.mount(app)
```

Three lines of that file deserve a note.

`model_modules` names **`sillo.users.base`**, not `sillo.users`. Model discovery
reads a module's own definitions, so the package that re-exports `User` finds
nothing — and Tortoise says `Module "sillo.users" has no models` and carries on.

`Tortoise.init_models` links the foreign keys without opening a connection.
`mount` resolves every declaration against the models, so they have to be linked
before it runs, and `setup_record` only does that at start-up.

`admin.mount(app)` is where every declaration is checked. A start-up that gets
past this line has an admin whose every reference resolves.

## An account

```bash
sillo user:admin you@example.com     # or: warder create-admin app:admin
uvicorn app:app --reload
```

`Gate.staff()` is the default, and it matters: when the admin shares the
application's user model — the ordinary arrangement — every registered account
holds a session, and admitting anyone who has one hands over the database.
`is_staff` is the flag that separates the two, and both commands set it.

![The sign-in screen](./images/login.png)

## What you already have

`Resource(Student)` names one model and nothing else, and you get:

![A derived list](./images/list.png)

A list with the columns the model has, a search box over its text columns, a
filter per state column, sensible ordering, paging, selection, CSV and JSON
export — and a form and a detail page to match.

Everything derived is replaced by naming it. The next page is about how.

## The full example

Every screenshot in this manual comes from a school management platform in one
file: thirteen models, roles, row-level scope, a many-to-many, actions that
collect input, two custom pages and a dashboard. It is in the Warder repository
as `app.py`, and it is what the tests run against.
