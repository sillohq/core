---
title: Console Commands
description: "Build your project's command-line tooling with sillo.console: command classes, explicit arguments, colour, tables, progress bars, and interactive prompts, with no third-party dependency."
head:
- tag: meta
  attrs:
    property: og:title
    content: Console Commands in Sillo
- tag: meta
  attrs:
    property: og:description
    content: Command classes, explicit arguments, colour, tables, and interactive prompts, built on the standard library alone.
---

#  Console Commands

Sillo ships a `sillo` command. A project writes no console file: it registers
commands on its application, and `sillo` finds them there.

Everything else follows from the application too. The database manager
`setup_record` put on `app.state` brings the migration and account commands; the
scheduler `setup_scheduler` put there brings the schedule commands; the user
model it authenticates against is the one accounts are created in. Nothing is
configured twice.

`sillo.console` is what both are built on. It gives you a command class,
explicit parameter declaration, a dispatcher, and the output and prompt
primitives that make a console readable. The file, the command set and the names
stay yours — the framework supplies the operations, the project decides what to
call them.

Nothing in the package imports anything outside the standard library. There is
no extra to install and no dependency to audit.

##  Registering a command

Write the class, register it on the application:

```python
# app/main.py
from sillo import SilloApp
from sillo.console import Command

app = SilloApp()


@app.add_command
class Greet(Command):
    name = "app:greet"
    help = "Say hello"

    async def handle(self):
        self.success("Hello.")
```

```bash
sillo                     # the listing, including app:greet
sillo app:greet           # run it
sillo app:greet -h        # this command's help
```

For a one-liner, the decorator form skips the class:

```python
@app.command("cache:clear", help="Drop every cached entry")
async def clear(command):
    await cache.flush()
    command.success("Cache cleared.")
```

###  Where the application is looked for

`SILLO_APP` first, then `[tool.sillo] app` in `pyproject.toml`, then
`app.main:app`, `main:app`, `app:app`. Outside a project none of those resolve
and only the framework commands are offered.

```toml
# pyproject.toml
[tool.sillo]
app = "app.main:app"
```

##  Commands

A command is a class with a name, an optional parameter list, and a `handle`
method. `handle` may be `async def` or `def` — both work.

```python
from sillo.console import Argument, Command, Flag, Option


class CreateAdmin(Command):
    """Create an administrator account.

    The password is read interactively unless ADMIN_PASSWORD is set.
    """

    name = "user:admin"
    help = "Create an administrator"
    aliases = ["admin"]

    arguments = [
        Argument("email", help="Address to create the account under"),
        Argument("username"),
        Option("role", default="admin", choices=["admin", "owner"]),
        Flag("force", short="f", help="Overwrite an existing account"),
    ]

    async def handle(self):
        password = self.secret("Password", confirm=True)
        user = await create_admin(
            self.argument("email"),
            self.argument("username"),
            password,
            role=self.option("role"),
        )
        self.success(f"Created {user.email}")
```

| Attribute | What it does |
|---|---|
| `name` | How the command is invoked. A colon groups it in the listing. |
| `help` | One line, shown in the listing. Falls back to the docstring's first line. |
| `description` | The longer text in `--help`. Falls back to the whole docstring. |
| `arguments` | What the command accepts. |
| `aliases` | Other names that dispatch here. |
| `hidden` | Keep it out of the listing. It still runs. |

Return an exit code from `handle`, or return nothing and let a clean run report
success.

###  Grouping

The part of a name before the colon is its group, and the listing sorts by it.
`db:migrate`, `db:make` and `db:rollback` appear together under **DB** with no
extra wiring.

##  Arguments, options and flags

Parameters are declared explicitly, in one list.

```python
arguments = [
    Argument("target"),                        # positional, required
    Argument("name", default="latest"),        # positional, optional
    Argument("files", variadic=True),          # collects the rest into a list
    Option("limit", type=int, default=50),     # --limit 20
    Option("queue", multiple=True),            # repeatable, comes back a list
    Flag("fake"),                              # --fake
    Flag("color", default=True),               # --no-color turns it off
]
```

Read them back with the accessor that matches the kind:

```python
self.argument("target")
self.option("limit")
self.flag("fake")
```

Three accessors rather than one is deliberate. Reading `self.option("fake")`
when `fake` was declared as a flag is a mistake worth a message, not a silently
wrong value:

```
KeyError: 'fake' is declared as flag, not option; read it with .flag('fake')
```

###  What the parser accepts

```bash
--limit 20      --limit=20      -l 20      -l20
--fake          -f              -abc                # bundled short flags
--no-color                                          # negating a default-on flag
-- --raw args                                       # stops option parsing
```

Anything after `--` is available as `self.extra`, for a command that forwards
its tail to another process.

###  Conversion and validation

`type` is any callable that raises `ValueError` or `TypeError` on bad input, so
`int`, `float` and `pathlib.Path` all work as they are. `choices` is checked
after conversion.

```python
Option("port", type=int, choices=[80, 443])
```

```
$ sillo serve --port 22
✗ port: '22' is not one of 80, 443
  Usage: sillo serve [options]
```

##  Output

Every command has the output helpers on `self`:

```python
self.line("plain text")
self.info("something worth noticing")
self.success("done")
self.warn("that was close")
self.error("that did not work")
self.muted("secondary detail")
self.blank()
```

###  Tables

```python
self.table(
    ["id", "email", "role"],
    [[user.id, user.email, user.role] for user in users],
    align=["right", "left", "left"],
)
```

Columns size themselves to the widest cell and shrink proportionally if the
total would overflow the terminal. Widths are measured with escape sequences
stripped, so a coloured cell lines up with a plain one.

###  Panels, rules and pairs

```python
self.panel("Migrations are up to date.", title="Database")
self.rule("Workers")
self.output.pairs([("Host", config.host), ("Port", config.port)])
```

###  Progress and spinners

```python
with self.progress(total=len(rows), label="Importing") as bar:
    for row in rows:
        await insert(row)
        bar.advance()

with self.spinner("Connecting"):
    await database.connect()
```

Both degrade. Piped into a file, the bar prints a line per ten per cent instead
of four hundred redraw frames, and the spinner prints its label once.

##  Asking questions

```python
name = self.ask("Project name", default="my-app")
email = self.ask("Email", validate=lambda value: "@" in value or "Not an address.")
password = self.secret("Password", confirm=True)

if self.confirm("Run migrations now?", default=True):
    ...

driver = self.choice("Database", ["sqlite", "postgres", "mysql"])

queues = self.multichoice(
    "Which queues should this worker serve?",
    [("mail", "Mail"), ("reports", "Reports")],
    defaults=["mail"],
    minimum=1,
)
```

`choice` and `multichoice` take over the terminal and redraw as the arrow keys
move. Space toggles in `multichoice`, Enter accepts, Escape or Ctrl-C cancels.
Once a list runs past eight options, typing filters it.

###  Validators check; they do not transform

A validator returns `None` or `True` to accept, returns a string or `False` to
reject, or raises `ValueError`. It does not replace the value.

That restriction exists because a validator like `lambda value: value.lower()`
returns a string, and a string is how a rejection carries its message. One
meaning has to win, and silently treating a normalised answer as an error
message is the worse failure. Normalise after `ask` returns.

###  Destructive actions

```python
if not self.prompt.confirm_destructive(
    "This drops every table in production.", "production"
):
    return 1
```

The user has to type the phrase back. Muscle memory cannot approve it.

##  Running without a terminal

Every prompt has a defined behaviour in CI, a cron job or a pipe:

| Prompt | Without a terminal |
|---|---|
| `ask` | Returns its default, or raises `UsageError` when it has none |
| `confirm` | Returns its default |
| `choice` | Returns its default, or raises `UsageError` when it has none |
| `multichoice` | Returns its defaults |
| `secret` | Always raises `UsageError` |
| `confirm_destructive` | Returns `False` |

Give a default to every prompt a command might hit unattended and the same
command works in both places. A `secret` never falls back — read it from the
environment instead.

Colour follows the usual rules: `NO_COLOR` disables it, `FORCE_COLOR` forces it,
`TERM=dumb` and a non-terminal stream disable it. Windows consoles get
virtual-terminal processing switched on.

##  Opening a database around a command

Override `context` to wrap `handle` in an async context manager. It is the
tidiest place for the connection that a whole family of commands needs:

```python
class DatabaseCommand(Command):
    """Base for commands that touch models."""

    def context(self):
        return database()


class ListUsers(DatabaseCommand):
    name = "user:list"
    help = "List users, newest first"

    arguments = [Option("limit", type=int, default=50)]

    async def handle(self):
        users = await list_users(model=User, limit=self.option("limit"))
        self.table(["id", "email"], [[u.id, u.email] for u in users])
```

The context closes even when the handler raises.

##  Failing

```python
self.fail("The database is unreachable.", exit_code=4)
```

That raises `CommandError`, which the console prints and turns into the exit
code. Anything unexpected is left alone and surfaces with its traceback, because
a programming error should not be flattened into a status.

| Situation | Exit code |
|---|---|
| Clean run | `0` |
| Unknown command, bad arguments | `2` |
| `self.fail(...)` | `1`, or whatever you pass |
| Cancelled prompt or Ctrl-C | `130` |

##  Commands sillo already provides

These come from the application, not from configuration you repeat:

```python
# app/main.py
from sillo import SilloApp
from sillo.record import DatabaseConfig, setup_record
from sillo.work.scheduler import setup_scheduler

app = SilloApp(auth_user_model=User)

database = setup_record(app, DatabaseConfig(...), model_modules=[...])
database.set_migrations("database.migrations")

scheduler = setup_scheduler(app)
```

That is all. `sillo` imports the application and offers what it found.

That is 23 commands, from six lines of setup you were writing anyway.

###  Database — from `setup_record`

| Command | What it does |
|---|---|
| `db:init` | Create the migration package |
| `db:make [name] [--apply]` | Write a migration from the current model changes |
| `db:migrate [--target] [--fake]` | Apply every pending migration |
| `db:plan [--target]` | Show which migrations would run |
| `db:rollback <target> [--fake] [-f]` | Roll back to a migration, or to `zero` |
| `db:sql <migration> [--backward]` | Show the SQL a migration would run |
| `db:status` | Show whether the database is up to date |

These appear when the application has a database. Set the migrations package on
the manager — `database.set_migrations("database.migrations")` — or `db:make`
has nowhere to write.

`db:rollback zero` unapplies everything, and asks you to type `zero` back before
it does. Without a terminal it refuses rather than assuming yes, so an
unattended run cannot drop the schema.

###  Accounts — from `setup_record` too

| Command | What it does |
|---|---|
| `user:create <email> <username> [--admin]` | Create a user |
| `user:admin <email> [username]` | Create an administrator |
| `user:list [-l] [--offset] [--staff]` | List users, newest first |
| `user:show <identifier>` | Show one account |
| `user:password <identifier>` | Change a password |
| `user:active <identifier> [--off]` | Activate or deactivate |
| `user:staff <identifier> [--revoke]` | Grant or revoke admin access |

**No model is required.** The commands use the application's
`auth_user_model` — set through `SilloApp(auth_user_model=…)` or through
`AuthenticationMiddleware(user_model=…)`, whichever you already use. With
neither, `sillo.users.commands` falls back to the built-in
`sillo.users.base.User`, so a project that has not defined its own still gets
working account management.

`identifier` is an email address or a username, and matches deactivated accounts
too — an account you cannot find is one you can never turn back on.

Passwords come from a hidden prompt, or from `SILLO_PASSWORD` when there is no
terminal. With neither, the command fails and says so rather than blocking on a
prompt nobody can answer.

###  Queues and the scheduler — from `setup_scheduler`

| Command | What it does |
|---|---|
| `queue:work [-q] [-c] [--timeout] [--max-jobs]` | Run the worker until stopped |
| `queue:list [-q]` | Show how much work is waiting on each queue |
| `queue:failed [-l] [--offset]` | List jobs that exhausted their retries |
| `queue:forget <id>` | Drop one failed job from the record |
| `queue:flush [-f]` | Drop every failed job from the record |
| `schedule:run` | Run scheduled tasks until stopped |
| `schedule:list` | List the registered tasks and their triggers |
| `schedule:pause <id>` / `schedule:resume <id>` | Stop and restart one task |

`queue:work` is also `worker`, and `schedule:run` is also `scheduler`.

Two things these commands tell you that a bare number would not:

**The queue may not be shared.** Without a `redis://` URL the queue lives in the
worker's own process, so nothing a web process dispatches ever reaches it.
`queue:work` and `queue:list` say so instead of sitting at zero looking healthy.

**Failures may not be durable.** The failed-job repository defaults to the
in-memory one, which is empty in a fresh process. `queue:failed` reports that
distinction rather than printing "no failures" at somebody about to stop
looking. Bind a durable repository with `failed=` to read the worker's.

The `schedule:` commands need a manager, which `setup_scheduler(app)` puts on
`app.state`. Without one they say so rather than reporting an empty schedule.

###  Registering only some of them

Every factory takes `only=`:

```python
console.add_many(record_commands(database, only=["db:migrate", "db:make"]))
```

A name the factory does not define is rejected at registration with the list of
ones it does, rather than silently producing a smaller console.

###  Renaming or replacing one

The factories are a convenience, not a requirement. The operations underneath
are public — `sillo.record.commands`, `sillo.users.commands` and
`sillo.work.commands` — so a project that wants different names, different
output or different arguments writes its own command and calls them directly.
That is the same split as everywhere else in sillo: the framework owns the
operation, the project owns the interface.

##  Short commands as functions

The class form is primary. For one-liners where a class is more ceremony than
the command is worth:

```python
@console.command("cache:clear", help="Drop every cached entry")
async def clear(command):
    await cache.flush()
    command.success("Cache cleared.")
```

The function receives the command instance, so the same accessors and output
helpers are available.

##  Testing a console

`run` returns an exit code instead of calling `sys.exit`, and every stream is
injectable, so a console is testable without a subprocess:

```python
import io

from sillo.console import Console, strip_ansi


def test_the_command_lists_users():
    stream = io.StringIO()
    console = Console(
        output=stream,
        error=stream,
        color=False,
        interactive=False,
    )
    console.add(ListUsers)

    assert console.run(["user:list", "--limit", "5"]) == 0
    assert "ada@example.com" in strip_ansi(stream.getvalue())
```

`interactive=False` makes every prompt take its default. To drive a menu
instead, pass the keys through `input`:

```python
console = Console(input=io.StringIO("\x1b[B\n"), interactive=True, ...)
```

##  A full console

```python
from sillo.console import Argument, Command, Console, Flag, Option

from database.config import database
from database.models.user import User


class DatabaseCommand(Command):
    def context(self):
        return database()


class Migrate(Command):
    name = "db:migrate"
    help = "Create the database and apply every pending migration"

    arguments = [Flag("fake", help="Record without running the SQL")]

    async def handle(self):
        from sillo.record.commands import migrate

        with self.spinner("Migrating"):
            await migrate(database(), fake=self.flag("fake"))
        self.success("Database is up to date.")


class CreateAdmin(DatabaseCommand):
    name = "user:admin"
    help = "Create an administrator"

    arguments = [Argument("email"), Argument("username")]

    async def handle(self):
        from sillo.users.commands import create_admin

        password = self.secret("Password", confirm=True)
        try:
            user = await create_admin(
                self.argument("email"),
                self.argument("username"),
                password,
                model=User,
            )
        except ValueError as error:
            self.fail(str(error))

        self.success(f"Created {user.email} — sign in at /admin/")


class ListUsers(DatabaseCommand):
    name = "user:list"
    help = "List users, newest first"

    arguments = [
        Option("limit", type=int, default=50),
        Flag("staff", help="Only administrators"),
    ]

    async def handle(self):
        from sillo.users.commands import list_users

        users = await list_users(
            model=User, limit=self.option("limit"), staff_only=self.flag("staff")
        )
        if not users:
            self.muted("No users yet.")
            return

        self.table(
            ["id", "email", "username", "admin"],
            [[u.id, u.email, u.username, "yes" if u.is_staff else ""] for u in users],
            align=["right", "left", "left", "center"],
        )


app.add_command(Migrate)
app.add_command(CreateAdmin)
app.add_command(ListUsers)
```

##  Building a console of your own

`sillo` is the ordinary path. Building a `Console` by hand is still there for
the cases it does not cover — a tool that ships separately from the
application, or one that should not import it at all:

```python
from sillo.console import Console

console = Console(prog="python tools.py", description="Release tooling.")
console.add_many([Package, Publish])

if __name__ == "__main__":
    console.main()
```

`run` returns an exit code rather than calling `sys.exit`, and every stream is
injectable, which is what makes a console testable without a subprocess.

##  What lives where

| Module | What it holds |
|---|---|
| `sillo.console` | `Command`, `Console`, `Argument`, `Option`, `Flag` |
| `sillo.console.output` | `Output`, `ProgressBar`, `Spinner` |
| `sillo.console.prompt` | `Prompt` |
| `sillo.console.style` | `Style`, `Palette`, `strip_ansi`, the semantic palette |
| `sillo.console.terminal` | Capability detection, `Key`, raw-mode key reading |
| `sillo.console.exceptions` | `UsageError`, `CommandError`, `Abort` |
