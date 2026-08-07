---
title: Project Structure
description: Every directory in a Sillo project, what belongs in it, and the reasoning behind the boundaries — app, database, routes, templates, static, storage, scripts, tests.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Project Structure
  - tag: meta
    attrs:
      property: og:description
      content: Every directory in a Sillo project, what belongs in it, and the reasoning behind the boundaries.
---

#  Project Structure

```text
myapp/
  app/
    main.py           ASGI entrypoint — `uvicorn app.main:app`
    bootstrap.py      Application assembly. Start reading here
    config.py         Typed settings, loaded from the environment
    admin.py          Admin panel registration
    templating.py     Jinja setup
    jobs/             Queue jobs
    tasks/            Scheduled tasks
  database/
    config.py         How this project connects — app and migrations share it
    models/           Your models. `user.py` is provided
    migrations/       Generated migrations — commit these
  routes/
    web.py            Server-rendered pages
    auth.py           JSON auth endpoints
    api.py            Everything else under /api
  templates/          Jinja templates
  static/             CSS, images, anything served as-is
  storage/            Runtime data — the SQLite file, logs, uploads
  scripts/
    smoke.py          Boots the app and hits every route
  tests/
  Makefile
  pyproject.toml
  .env.example
```

Four top-level packages, and the split between them is the point of this
page.

##  The shape of it

**`app/` is the application.** How it is assembled, how it is configured,
what runs in the background. Nothing in `app/` is about a URL or a table.

**`database/` is the data layer.** The connection, the models, the
migrations — one directory holding everything that describes persistence.

**`routes/` is the HTTP surface.** What paths exist and what they return.

**`sillo` is the operator's entry point.** Migrations, accounts,
processes. The project ships no console file: `sillo` finds the application
and derives its commands from what the application set up.

That boundary is load-bearing in one direction: `routes/` imports from
`app/` and `database/`, `app/` imports from `database/`, and `database/`
imports from neither. Follow it and a model can be used from a script, a
test or a migration without dragging the HTTP layer in behind it.

---

##  `app/`

###  `app/main.py`

The ASGI entrypoint, and deliberately trivial:

```python
from app.bootstrap import create_app

app = create_app()
```

`uvicorn app.main:app` is what your process manager runs. Keeping it a
one-liner is what lets tests build their own instance:

```python
from app.bootstrap import create_app

app = create_app()          # a fresh one, with no shared state
```

A module that builds the app *and* configures logging *and* reads
arguments cannot be imported twice safely. This one can.

###  `app/bootstrap.py`

The single place where the application is put together. Read it first.

```python
def create_app() -> silloApp:
    application = silloApp(debug=config.debug, title=config.app_name, version="0.1.0")

    _register_admin(application)
    _register_templating()
    _register_middleware(application)
    _register_database(application)
    # _register_work(application)
    _register_static(application)
    _register_routes(application)

    return application
```

Every step is a named function with its reasoning in the docstring. The
order is not cosmetic, and one part of it is genuinely surprising:

<aside>

**Middleware order is inside-out.** `application.use()` puts the newest
registration *outermost*, so whatever registers **last runs first** at
request time.

`AdminSite.mount()` attaches its own auth middleware through
`app.use()`, and that middleware reads `request.session`. So the admin
has to be registered **before** the middleware block — which is what
leaves the session middleware outside, and therefore ahead of it.
Register the admin after, and every admin page 500s with "No Session
Middleware Installed" while the session middleware is demonstrably
installed.

</aside>

The same ordering has a second consequence, and it catches people writing
framework code rather than application code: the admin's startup hook is
registered before the database's, so **the admin's hook runs while the ORM
is still uninitialised**. Anything that asks the database a question at
that moment gets the wrong answer.

###  `app/config.py`

Typed settings, read from the environment once at import.

```python
class Settings:
    app_name: str = "Myapp"
    app_env: Literal["local", "testing", "staging", "production"] = "local"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    secret_key: str = "change-me"

    database_url: str = "sqlite://storage/myapp.db"
    db_pool_size: int = 5
    db_echo: bool = False
    db_generate_schemas: bool = False

    session_cookie_name: str = "session_id"
    session_lifetime: int = 86400

    admin_enabled: bool = True
    admin_prefix: str = "/admin"

    cors_allow_origins: str = "http://localhost:5173"
    log_level: Literal["debug", "info", "warning", "error"] = "info"
```

Read values through `config`, never `os.getenv`:

```python
from app.config import config

config.database_url
```

A typo in a variable name then fails at startup with a clear message,
instead of becoming `None` at request time and failing three layers down
in something that looks unrelated.

<aside>

**`db_generate_schemas` is `False` on purpose.** Schema generation issues
DDL on every startup, which creates tables outside the migration history —
so a later `make migration` sees them as new and writes a migration that
then fails to apply against tables that already exist. It also has every
process do it at once: an app, a worker and a scheduler sharing one SQLite
file will raise "database is locked" on boot.

Migrations own the schema. See
[Database & Migrations](/guides/start/database/).

</aside>

###  `app/admin.py`

Where admin models are registered. One function, called from bootstrap:

```python
def register_admin(application: silloApp) -> AdminSite:
    admin = AdminSite(title="Myapp Admin", prefix=config.admin_prefix, user_model=User)

    @admin.register(User)
    class UserAdmin(ModelAdmin):
        verbose_name = "Users"
        list_display = ["id", "email", "username", "is_active", "is_staff", "last_login"]
        search_fields = ["email", "username"]

    admin.mount(application)
    return admin
```

Register your models **before** `admin.mount()`. Mounting registers the
user model with a default presentation if nothing has claimed it yet, so
registering yours first is what lets your columns take effect.

See [The Admin Panel](/guides/start/admin/).

###  `app/templating.py`

Configures the Jinja environment. `create_app` calls it before any page
renders — without that, `sillo.templating.render` raises
`NotImplementedError`. Not optional for a project serving HTML.

###  `app/jobs/`

Queue jobs. An empty package in a new project.

Import each job class in `__init__.py`. The worker resolves a queued
payload by importing the module the payload names, so a job in a module
nobody imports would still be found — but one place to look is how you
find them later, and it is what lets payloads queued by older releases,
which recorded only a class name, still resolve.

A job must be a **module-level class**. One defined inside a function, or
in a script run as `__main__`, cannot be imported by a separate worker
process. See [Background Work](/guides/start/background-work/).

###  `app/tasks/`

Scheduled tasks, registered in one function:

```python
def register_tasks(scheduler) -> None:
    from sillo.work.scheduler import CronTrigger
    from app.tasks.cleanup import cleanup

    scheduler.schedule(cleanup, trigger=CronTrigger("0 3 * * *"), name="cleanup")
```

Both the application and a standalone scheduler call it, so both see the
same schedule. Add a task in two places and they will drift.

---

##  `database/`

Everything about persistence, in one directory: how you connect, what the
shapes are, and how they got that way.

###  `database/config.py`

One definition of how the project connects, shared by the running
application, the migration commands, and any script that opens the
database.

```python
MODEL_MODULES = ["database.models", "sillo.admin.models"]
MIGRATIONS_MODULE = "database.migrations"


def database_config() -> DatabaseConfig:
    return DatabaseConfig(
        url=config.database_url,
        pool_size=config.db_pool_size,
        echo=config.db_echo,
        generate_schemas=config.db_generate_schemas,
    )


def database() -> DatabaseManager:
    manager = DatabaseManager(database_config())
    manager.register_models(*MODEL_MODULES).set_migrations(MIGRATIONS_MODULE)
    return manager
```

There is no separate migration configuration. Change the connection here
and migrations follow, with nothing to keep in step by hand.

It is also how a script of your own opens the database:

```python
from database.config import database

async with database():
    await User.all()
```

<aside>

**`MODEL_MODULES` is a short list on purpose.**

`sillo.admin.models` is the admin's activity log — who changed what, and
when. It is the one table the admin brings, and it is worth having from
the first day rather than after the first incident.

What is deliberately absent is `sillo.admin.default_user`, which holds the
admin's fallback `AdminUser` and its roles. Registering it would put a
second set of accounts beside `users` to keep in step, or to forget about.
The admin signs people in with *your* `User`.

Do not add `sillo.users` either — models are keyed by class name, so the
framework's built-in `User` would displace your own and your extra columns
would silently stop being created.

</aside>

###  `database/models/`

Your models, one per file, imported in `__init__.py`.

```python
# database/models/__init__.py
from database.models.user import User

__all__ = ["User"]
```

The ORM only sees what is imported there. A model it cannot see fails on
first query with `default_connection cannot be None` — which points at the
database rather than at the missing import, and is the single most
confusing error in a new project.

###  `database/migrations/`

Generated migrations. **Commit them.** They are the schema's source of
truth, and the database file is gitignored precisely so that they have to
be.

They are excluded from linting: they are engine output, and formatting
generated code makes `make check` fail the first time you add a model.

---

##  `routes/`

Three modules, split by what they return rather than by feature — a
project small enough to have one `routes/` directory is better served by
"HTML here, JSON there" than by a package per noun.

| Module | |
| --- | --- |
| `web.py` | Server-rendered pages |
| `auth.py` | JSON auth endpoints: register, login, logout, me |
| `api.py` | Everything else under `/api` |

<aside>

**A prefix-less router swallows everything.** Mounting a `Router` with no
prefix claims `""` and every path beneath it — including routes registered
later during startup, like the admin's.

Root-level pages are therefore registered individually:

```python
application.get("/", handler=web.welcome, name="welcome")
```

And when mounting routers, **order matters**: a router claims its whole
prefix subtree, so mount the most specific prefix first. Mounting `/api`
before `/api/auth` leaves every auth route unreachable.

</aside>

---

##  `templates/` and `static/`

Jinja templates and files served as-is.

`/static` is mounted in `bootstrap.py` for development and small
deployments. With a proxy in front it never sees traffic — see
[Deployment](/guides/start/deployment/#static-files).

<aside>

**`StaticFiles` takes no prefix.** The prefix comes from the `Group` that
mounts it:

```python
Group(path="/static", app=StaticFiles(directory="static"))
```

Passing a prefix to `StaticFiles` itself is silently ignored, and every
asset 404s at a path that looks right in the template.

</aside>

---

##  `storage/`

Runtime data: the SQLite file, logs, uploads, caches. Tracked as a
directory, ignored as contents.

```gitignore
storage/logs/*
storage/cache/*
storage/temp/*
storage/app/*
!storage/**/.gitkeep

storage/*.db
storage/*.db-shm
storage/*.db-wal
```

<aside>

**The `-shm` and `-wal` entries are not decoration.** Committing SQLite's
write-ahead log leaves a fresh clone with a WAL referring to a database
that is not there, which SQLite reports as `disk I/O error` — an alarming
message for what is actually a stale file.

</aside>

---

##  Management commands

There is no console file. `sillo` finds the application — `app/main.py` here —
and offers what it set up: `setup_record` brings the migration and account
commands, `setup_scheduler` brings the schedule commands.

```bash
uv run sillo db:migrate
uv run sillo user:admin ada@example.com ada
uv run sillo queue:work
```

Commands of your own go on the application with `app.add_command`, which is
what puts them in the same listing.

See [The Console](/guides/start/console/).

---

##  `scripts/` and `tests/`

`scripts/smoke.py` boots the application and calls every route. It is not
a unit test and it is not a replacement for one — it exists because a
project can import cleanly, render every template and still fail on the
first real request.

`tests/` holds the pytest suite. `conftest.py` gives every test its own
temporary database.

Both are covered in [Testing](/guides/start/testing/).

---

##  Adding your own

The layout is a starting point, not a rule. Two boundaries are worth
keeping as you grow:

**Keep `database/` importable on its own.** If a model starts importing
from `routes/`, a migration that touches that model now needs the HTTP
layer to import cleanly. Push shared logic down, not up.

**Keep `bootstrap.py` a list of steps.** When assembly grows, add a
`_register_*` function; do not inline it. The value of that file is that
you can read the whole application's shape in twenty lines.

For anything larger — a package per domain, with its own models, routes
and services — move `routes/` and `database/models/` into those packages
and keep `bootstrap.py` and `database/config.py` where they are. Those two
are the project's spine.

##  Related

- [Creating a Project](/guides/start/) — how the files got here
- [The Console](/guides/start/console/) — every command in full
- [Database & Migrations](/guides/start/database/) — models and schema changes
- [Middleware](/guides/middleware/) — the ordering rules in general
- [Routers & Sub-Apps](/guides/routers-and-subapps/) — mounting and prefixes
