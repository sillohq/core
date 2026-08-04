---
title: The Console
description: console.py — every command a Sillo project ships with, how it is built on the framework's command functions, and how to add your own.
head:
  - tag: meta
    attrs:
      property: og:title
      content: The Sillo Project Console
  - tag: meta
    attrs:
      property: og:description
      content: console.py — every command a Sillo project ships with, and how to add your own.
---

#  The Console

Sillo ships **no command-line interface**. A project brings its own, and
in a project created from the starter that is `console.py` at the root.

```bash
uv run python console.py
```

with no arguments prints everything below.

##  Why the project owns it

Building a CLI means choosing an argument parser, an output format and a
set of names. Those are an application's decisions.

What a framework owes you is the *operations*, callable from anywhere:

```python
from sillo.record.commands import init, make, migrate, plan, rollback, sql
from sillo.users.commands import create_user, create_admin, list_users, set_password
from sillo.work.commands import run_worker, run_scheduler, build_worker
```

`console.py` is a thin layer over those — about three hundred lines,
mostly `argparse` wiring and print statements. It has **no dependency
beyond sillo**; `argparse` ships with Python.

That has a consequence worth stating plainly: **nothing in your project
depends on a tool you have to keep installed.** `sillo-start` creates the
project and is then irrelevant. The console cannot rot when a separate CLI
changes, because there is no separate CLI.

##  Always run it through `uv run`

```bash
uv run python console.py db migrate     # correct
python console.py db migrate            # depends on what is activated
```

A virtual environment activated in a parent directory shadows the
project's own, and bare `python` finds whatever sillo lives there. When
that is older than the project needs, the failure lands deep inside your
own files:

```text
File "myapp/database/config.py", line 65, in database
    manager.register_models(*MODEL_MODULES).set_migrations(MIGRATIONS_MODULE)
AttributeError: 'NoneType' object has no attribute 'set_migrations'
```

which reads like a bug in your project and is not — chained registration
simply did not exist in that release.

`console.py` checks for this before doing anything and reports it
properly:

```text
This project needs a newer sillo-framework than the one being used.

  version:      0.0.1a3
  installed at: /Users/you/.venv/lib/python3.12/site-packages/sillo
  python:       /Users/you/.venv/bin/python
  missing:      sillo.record.commands.init, ...

That python is probably not this project's. Run commands through uv, which
always uses it:

  uv run python console.py ...
  make migrate
```

The check is by **capability, not version number** — what matters is
whether the call will work, which needs no version arithmetic.

---

##  Database

```bash
uv run python console.py db migrate [--fake]
uv run python console.py db make [name] [--apply]
uv run python console.py db plan
uv run python console.py db rollback <target>
```

###  `db migrate`

Creates the database and applies every pending migration.

```console
$ uv run python console.py db migrate
models: database.migrations -> /myapp/database/migrations
  Created models.0001_initial
    /myapp/database/migrations/0001_initial.py
Database is up to date.
```

On a project with no migrations yet it does three things: creates the
migration package, writes `0001_initial` from your models, and applies it.
Afterwards it only applies what is pending.

**There is no `db init`.** One command either way means there is no state
in which you have to know which to reach for.

```python
async def db_migrate(args) -> int:
    package = Path(MIGRATIONS_MODULE.replace(".", "/"))
    if not any(package.glob("0*.py")):
        # Nothing written yet: set the package up and record the starting
        # schema, so a later model change is an alteration of a known table
        # rather than a table the migration engine has never seen.
        await init(database())
        await make(database(), "initial")

    await migrate(database(), fake=args.fake)
```

`--fake` records migrations as applied **without running the SQL**. It is
for adopting a schema that already exists — a project that ran on
`generate_schemas` has the tables but no history:

```bash
uv run python console.py db make initial
uv run python console.py db migrate --fake
```

The schema is now under migration control, and the next model change is an
alteration of a known table rather than a table the engine has never seen.

###  `db make`

Writes a migration describing your current model changes.

```bash
uv run python console.py db make add_posts           # write it
uv run python console.py db make add_posts --apply   # write and apply
```

Without `--apply` it stops and tells you to look:

```text
Written. Review it, then: python console.py db migrate
```

That pause is the point. See
[Database & Migrations](/guides/start/database/#always-read-the-generated-migration)
for what the diff engine gets wrong.

Writing nothing is a valid outcome — if the models already match the last
migration, there is nothing to record.

###  `db plan`

Shows what would run, without running it.

```bash
uv run python console.py db plan
```

Prints `Nothing pending.` when the database is current.

###  `db rollback`

```bash
uv run python console.py db rollback 0001_initial   # back to this migration
uv run python console.py db rollback zero           # unapply everything
```

**`target` is required.** There is no implicit "one step back" — you name
the migration to stop at, or `zero`. A bare name is qualified with the app
label for you, so `0001_initial` works as well as `models.0001_initial`.

---

##  Users

```bash
uv run python console.py user create <email> <username>
uv run python console.py user admin  <email> <username>
uv run python console.py user list [--limit N] [--staff]
uv run python console.py user password <identifier>
```

###  `user create` and `user admin`

```console
$ uv run python console.py user admin ada@example.com ada
Password:
Created ada@example.com — sign in at /admin/
```

`admin` is `create` plus `is_staff` and `is_superuser` — the flags that
get an account into `/admin/`.

The password is prompted for, hidden. For scripts and CI, set
`ADMIN_PASSWORD`:

```bash
ADMIN_PASSWORD='Hunter2!pass' uv run python console.py user admin ci@example.com ci
```

The policy is enforced by the framework and reports exactly what failed:

```console
$ ADMIN_PASSWORD=short uv run python console.py user admin weak@example.com weak
Password must be at least 8 characters. Password must contain at least one
uppercase letter. Password must contain at least one digit. Password must
contain at least one special character.
```

The wording comes from `sillo.users.commands`, not from the console — one
place decides what a valid password is.

###  `user list`

```console
$ uv run python console.py user list
     3  A-  ada@example.com                  ada
     2  --  someone@example.com              someone
     1  AX  old-admin@example.com            olddev

  A = admin access, X = deactivated
```

Newest first. `--staff` filters to administrators, `--limit` caps the rows
(default 50).

The two flag columns are `is_staff` and `is_active`. An account showing
`AX` has admin rights and is deactivated — it cannot sign in, and clearing
that is a single field.

###  `user password`

```bash
uv run python console.py user password ada@example.com
uv run python console.py user password ada              # username works too
```

Takes an email **or** a username. Deactivated accounts are findable — you
frequently need to reset a password precisely because an account was
disabled.

---

##  Processes

```bash
uv run python console.py worker [--queues a,b] [--concurrency N]
uv run python console.py scheduler
uv run python console.py serve [--host H] [--port P] [--reload]
```

###  `worker`

```bash
uv run python console.py worker
uv run python console.py worker --queues urgent,default --concurrency 8
```

`--queues` is highest-priority-first. `--concurrency` defaults to 4. The
broker comes from `QUEUE_URL`; with it unset the queue is in-process.

<aside>

**With the default in-memory queue, a separate worker processes nothing.**
`SyncConnection` lives inside one process, so `console.py worker` has its
own empty queue while your application dispatches into a different one.

Either run the worker inside the application
(`_register_work(application, in_process=True)`) or set
`QUEUE_URL=redis://…` so both processes talk to the same broker. See
[Background Work](/guides/start/background-work/).

</aside>

It imports `app.jobs` before starting, so queued payloads resolve back to
the classes that handle them.

###  `scheduler`

Runs `app.tasks.register_tasks` and blocks. Both this and the application
call the same function, so a task added in one place is seen by both.

###  `serve`

```bash
uv run python console.py serve --reload
uv run python console.py serve --host 0.0.0.0 --port 9000
```

Single-process uvicorn, defaulting to `config.host` and `config.port`.
It is the development server; production uses `make serve`, which is
uvicorn with `--workers 4`. See
[Deployment](/guides/start/deployment/).

---

##  Make targets

Everything above has a `make` equivalent, and CI uses those:

| Target | Runs |
| --- | --- |
| `make migrate` | `db migrate` |
| `make migration m="add_posts"` | `db make "add_posts" --apply` |
| `make plan` | `db plan` |
| `make rollback to=0001_initial` | `db rollback 0001_initial` |
| `make admin e=… u=…` | `user admin` |
| `make users` | `user list` |
| `make worker` | `worker` |
| `make scheduler` | `scheduler` |
| `make dev` | `serve --reload` |
| `make serve` | `uvicorn --workers 4` |

`make admin` and `make rollback` check their arguments first:

```console
$ make admin
  need both: make admin e=ada@x.com u=ada
```

Without that guard the console receives empty strings and reports a
validation failure about an empty email — which says nothing about the
missing argument.

---

##  How a command is built

Three parts: a function, a parser entry, and the dispatcher.

###  The function

```python
async def db_plan(args) -> int:
    """Show which migrations would run."""
    from sillo.record.commands import plan

    lines = await plan(database())
    print("\n".join(lines) if lines else "Nothing pending.")
    return 0
```

Takes the parsed arguments, returns an exit code. The framework import is
inside the function so that starting the console does not import the
world — `console.py --help` should not open a database connection.

###  The parser entry

```python
plan_cmd = schema.add_parser("plan", help="Show which migrations would run.")
plan_cmd.set_defaults(run=db_plan)
```

`set_defaults(run=…)` is how the dispatcher finds the function.

###  The dispatcher

```python
if asyncio.iscoroutinefunction(args.run):
    if getattr(args, "needs_database", False):
        return asyncio.run(_with_database(args.run(args)))
    return asyncio.run(args.run(args))
return args.run(args)
```

Three cases: a synchronous command (`serve`, which hands the loop to
uvicorn), an async command that manages its own connections (the migration
commands do), and an async command that needs the ORM open.

That last one is the interesting flag:

```python
async def _with_database(coroutine):
    async with database():
        return await coroutine
```

`sillo.users.commands` operates on models and assumes the ORM is already
initialised — that is the application's job, and here it is the console's.
Migrations are the exception: they open and close their own connections,
so wrapping them would nest two.

Commands that touch models declare it:

```python
list_cmd.set_defaults(run=user_list, needs_database=True)
```

Forget it and the command fails with `default_connection cannot be None`.

---

##  Adding your own

A command that backfills a column, in full:

```python
# -- maintenance -------------------------------------------------------


async def backfill_slugs(args) -> int:
    """Give every post without a slug one."""
    from database.models.post import Post

    posts = await Post.filter(slug=None).limit(args.limit)
    for post in posts:
        post.slug = slugify(post.title)
        await post.save()

    print(f"Updated {len(posts)} post(s).")
    return 0
```

Register it in `build_parser()`:

```python
backfill_cmd = commands.add_parser("backfill-slugs", help="Fill in missing slugs.")
backfill_cmd.add_argument("--limit", type=int, default=500)
backfill_cmd.set_defaults(run=backfill_slugs, needs_database=True)
```

```bash
uv run python console.py backfill-slugs --limit 100
```

Three rules, and they are the whole convention:

1. **Return an exit code.** `0` for success, non-zero for failure. CI and
   `make` depend on it.
2. **Set `needs_database=True`** if the command touches models.
3. **Import inside the function**, so `--help` stays instant.

For a group of related commands, mirror `db` and `user`:

```python
reports = commands.add_parser("reports", help="Generated reports.").add_subparsers(
    dest="action", metavar="<action>"
)

daily_cmd = reports.add_parser("daily", help="Yesterday's numbers.")
daily_cmd.set_defaults(run=reports_daily, needs_database=True)
```

<aside>

**Do not name a local variable after something at module level.** The
parser for `db` is called `schema`, not `database`, because `database` is
the module-level manager factory — shadowing it inside `build_parser()`
is a trap for the next edit.

</aside>

##  Errors and output

Commands that can fail on user input catch the framework's exception and
print its message:

```python
try:
    user = await create(args.email, args.username, password, model=User)
except ValueError as error:
    # The framework reports which rule failed — duplicate address, or which
    # part of the password policy. Its wording beats a local guess.
    print(error, file=sys.stderr)
    return 1
```

Errors to `stderr`, results to `stdout`, so `console.py user list > users.txt`
gives you the list and leaves the errors on your terminal.

Connect/disconnect logging is quieted for console commands:

```python
logging.getLogger("sillo.record").setLevel(logging.WARNING)
```

"Database connected" and "connections closed" around every `user list` is
noise. The application still logs them at startup, where they mean
something.

##  Related

- [Project Structure](/guides/start/structure/) — where `console.py` sits
- [Database & Migrations](/guides/start/database/) — what `db` drives
- [Users & Authentication](/guides/start/authentication/) — what `user` drives
- [Background Work](/guides/start/background-work/) — what `worker` drives
- [Deployment](/guides/start/deployment/) — running migrations on deploy
