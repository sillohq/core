---
title: Building a Console
description: "Assembling a command-line tool of your own with sillo.console — the Console object, the bundled command factories, binding a database, the function form, loops and exit codes."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Building a Sillo Console
  - tag: meta
    attrs:
      property: og:description
      content: Console, record_commands, user_commands, work_commands, and running it.
---

Most projects never need this. Registering a command on the application puts it
on `sillo`, and that is the shortest path.

Build a console of your own when you want a **different** command-line tool —
one with its own name, its own subset of commands, or one that does not depend
on importing a web application at all.

## The shape

```python
# tools.py
from sillo.console import Console
from app.commands import Backfill, Reindex

console = Console(
    prog="python tools.py",
    description="Maintenance tools.",
    version="1.0",
)
console.add(Backfill)
console.add(Reindex)

if __name__ == "__main__":
    console.main()
```

```bash
python tools.py --help
python tools.py posts:backfill --dry-run
```

`Console` owns exactly three decisions: which command a set of tokens names,
what the help looks like, and which exit code a failure produces. The file, the
command set and the names stay yours.

### Constructor

```python
Console(prog="console.py", description="", version=None,
        output=None, error=None, input=None,
        color=None, interactive=None)
```

`version` is what `--version` reports; omit it and the flag is not offered at
all. The three stream parameters and the two overrides exist for tests — see
[Testing](#testing) below.

## The bundled command factories

The framework's own command sets are factories, not fixed classes. Call one to
get commands bound to *your* database, model or broker:

```python
from sillo.record.console import record_commands
from sillo.users.console import user_commands
from sillo.work.console import work_commands
```

### `record_commands`

```python
record_commands(database, *, app="models", only=None)
```

```python
console.add_many(record_commands(database))
console.add_many(record_commands(database, only=["db:migrate", "db:status"]))
```

`database` is a `DatabaseManager` **or a callable returning one**. Both are
accepted rather than making you remember which — a project often exports a
factory rather than an instance. A callable is called on each access, not once
at registration, because a factory usually builds a fresh manager per
invocation and caching it here would share one connection across commands that
each expect their own.

`only` restricts the set. A name the module does not define raises at
registration and lists what it does define, so a typo fails at import rather
than at 3am.

`app` is the migration app label. Two model packages means two registrations:

```python
console.add_many(record_commands(database, app="models"))
console.add_many(record_commands(reporting, app="reporting", only=["db:migrate"]))
```

Each call generates a fresh subclass per command, so two consoles — or two
registrations in one console — can bind the same command to different databases
without the second overwriting the first.

### `user_commands`

```python
console.add_many(user_commands(model=Account, context=database))
```

`model` is the user model; omit it and `sillo.users.commands` falls back to the
built-in `User`, so the commands work on a project that has not defined one
yet.

`context` is an async context manager — or a callable returning one — opened
around every command. **This is the part that matters outside an application.**
The ORM has to be initialised before these touch a model, and in a standalone
console nothing has done that. Without it the first command fails inside
Tortoise rather than anywhere you would think to look.

### `work_commands`

```python
console.add_many(work_commands(
    url=os.getenv("QUEUE_URL"),
    queues=["mail", "default"],
    scheduler=lambda: manager,
    failed=lambda: failed_repository,
    context=database,
))
```

| Parameter | Meaning |
| --- | --- |
| `url` | Broker URL. `None` keeps the queue in-process. |
| `queues` | Consumed in priority order. Defaults to `["default"]`. |
| `prefix` | Redis key prefix. |
| `scheduler` | The `SchedulerManager`, or a callable returning one. |
| `failed` | A durable failed-job repository, or a callable returning one. |
| `context` | Opened around every command. |

Pass `failed=` if you want `queue:failed` to show anything. Without it the
commands use a fresh in-memory repository, which is empty in every new process
— and they say so rather than reporting "no failures" at someone about to go
home.

Omit `scheduler=` and the `schedule:*` commands still register but report what
is missing when run.

### `only`, on all three

All three factories take `only=` and behave the same way: a subset by name, and
a `ValueError` at registration listing the real names if one is misspelled.

```python
console.add_many(user_commands(only=["user:admin", "user:list"], context=database))
```

## Function form

For commands not worth a class:

```python
@console.command("cache:clear", help="Drop every cached entry")
async def clear(command):
    await cache.flush()
    command.success("Cache cleared.")
```

The function receives the command instance, so every accessor and output helper
is available. It takes the same `arguments`, `aliases` and `hidden` as a class:

```python
@console.command(
    "cache:forget",
    help="Drop one key",
    arguments=[Argument("key")],
)
async def forget(command):
    await cache.forget(command.argument("key"))
    command.success("Forgotten.")
```

The class form is the primary one and is what anything with a real body should
use. This is for the one-liners, where a class is more ceremony than the
command is worth.

## Running it

```python
console.run(argv=None)         # returns an exit code
await console.run_async(argv)  # same, on the current loop
console.main(argv=None)        # runs and raises SystemExit
```

`run` returns a status rather than calling `sys.exit`, so a test can assert on
it and an embedding program can decide for itself what to do next. `main` is
the thin wrapper for `if __name__ == "__main__"`.

Call `run_async` from inside a running loop. `run` raises a `RuntimeError`
naming the alternative rather than deadlocking:

```
Console.run() cannot be called while an event loop is running.
Use `await console.run_async(argv)` instead.
```

### Loops

`run` only creates an event loop for the commands that want one. An
`async def handle` runs inside `asyncio.run`; a plain `def handle` — one handing
the loop to something else, like `uvicorn.run` — runs with no loop in that
thread at all.

The dispatcher works this out from the method itself, so a command opts in
purely by how it is written.

## Registration rules

```python
console.add(Backfill)                    # raises on a duplicate name
console.add(Backfill, override=True)     # replaces
console.add_many([Backfill, Reindex])
```

A duplicate name or alias is an error by default, naming what already holds it.
`override=True` replaces the registration and every alias pointing at it — this
is how `sillo` lets a project's command win over a bundled one of the same
name.

## Help and unknown commands

The listing groups by the part of a name before its colon, sorts groups
alphabetically with the ungrouped ones first, and aligns the descriptions of
commands and global flags to one shared column.

An unknown command suggests the closest registered name:

```
Unknown command 'db:migrat'.
  Did you mean db:migrate?
  Run python tools.py --help for the list.
```

## Testing

```python
import io

out = io.StringIO()
console = Console(
    prog="tools.py",
    output=out,
    color=False,
    interactive=False,
)
console.add(Backfill)

assert console.run(["posts:backfill", "--dry-run"]) == 0
assert "Would update" in out.getvalue()
```

`color=False` removes the escape sequences; `interactive=False` makes every
prompt take its default. Both are how you get a command under test without a
terminal.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | `CommandError` — a command failed at its work |
| `2` | `UsageError` — bad input, or an unknown command |
| `130` | `Abort` — Ctrl-C |

## See also

- [Writing commands](/cli/custom-commands/)
- [Arguments, options and flags](/cli/arguments/)
- [Console internals](/advanced/console/) — how the dispatcher is built.
