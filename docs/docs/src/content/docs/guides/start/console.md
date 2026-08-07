---
title: The Console
description: The sillo command — every command a Sillo project gets, where they come from, and how to add your own.
head:
  - tag: meta
    attrs:
      property: og:title
      content: The Sillo Project Console
  - tag: meta
    attrs:
      property: og:description
      content: The sillo command — every command a Sillo project gets, and how to add your own.
---

#  The Console

A project created from the starter ships no console file. `sillo` finds the
application and derives its commands from it.

```bash
uv run sillo
```

with no arguments prints everything below.

##  Where the commands come from

The application already says what the project has, so nothing is configured
twice. `sillo` imports it and reads it:

| On the application | What it brings |
|---|---|
| `setup_record(app, …)` on `app.state["record"]` | `db:*` and `user:*` |
| `setup_scheduler(app)` on `app.state["scheduler"]` | `schedule:*` |
| `AuthenticationMiddleware(user_model=…)` | which model accounts are created in |
| `app.add_command(…)` | the project's own commands |

A project with no database gets no `db:*` — there is nothing to migrate. The
queue commands are always offered, because a queue needs no setup to inspect.

The starter wires the first three in `app/bootstrap.py`, so all of it is
available from the first `make setup`.

###  How the application is found

In order: the `SILLO_APP` environment variable, then `[tool.sillo] app` in
`pyproject.toml`, then `app.main:app`, `main:app`, `app:app`. The starter's
layout matches the first conventional name, so it needs no configuration.

```toml
# pyproject.toml — only if your application lives somewhere unusual
[tool.sillo]
app = "src/myapp/server.py:application"
```

Outside a project none of those resolve and only `version`, `serve` and
`routes` are offered.

##  Always run it through `uv run`

```bash
uv run sillo db:migrate     # correct
sillo db:migrate            # depends on what is activated
```

A virtual environment activated in a parent directory shadows the project's
own, and the sillo it finds there is usually older than the project needs.
`uv run` avoids the question entirely.

##  Database

```bash
uv run sillo db:migrate [--target] [--fake]
uv run sillo db:make [name] [--apply]
uv run sillo db:plan [--target]
uv run sillo db:rollback <target> [--fake] [-f]
uv run sillo db:status
uv run sillo db:sql <migration> [--backward]
uv run sillo db:init
```

###  `db:migrate`

Applies every pending migration, listing them first.

```bash
$ uv run sillo db:migrate
  • + models.0001_initial

✓ Applied 1 migration.
```

Nothing pending says so and changes nothing:

```bash
$ uv run sillo db:migrate
Nothing pending.
```

`--fake` records migrations as applied without running their SQL. That is for
adopting a schema that already exists — tables created before the project had
migrations — not for skipping one that fails.

###  `db:make`

Writes a migration describing the difference between the models and the last
migration.

```bash
uv run sillo db:make add_posts           # write it
uv run sillo db:make add_posts --apply   # write and apply
```

```
✓ Migration written.
  Review it, then: sillo db:migrate
```

When the models already match, nothing is written and it says so rather than
reporting a success for a file that does not exist:

```
No model changes to record.
```

###  `db:plan`

What `db:migrate` would do, without doing it. Worth running before a
deployment.

###  `db:status`

Whether the database is up to date.

```bash
$ uv run sillo db:status
  app      models
  pending  0

✓ Up to date.
```

###  `db:rollback`

```
  USAGE
    sillo db:rollback <TARGET> [options]

  ARGUMENTS
    TARGET        Migration to stop at, or 'zero'

  OPTIONS
    --fake        Record the rollback without running it
    -f, --force   Skip the confirmation
```

There is no implicit "one step back": name the migration to stop at. `zero`
unapplies everything, which drops the tables those migrations made — so it asks
you to type `zero` back before it does. Without a terminal it refuses rather
than assuming yes, which is what stops an unattended run from dropping a schema.

##  Users

```bash
uv run sillo user:admin <email> [username]
uv run sillo user:create <email> <username> [--admin]
uv run sillo user:list [-l] [--offset] [--staff]
uv run sillo user:show <identifier>
uv run sillo user:password <identifier>
uv run sillo user:active <identifier> [--off]
uv run sillo user:staff <identifier> [--revoke]
```

The account is created in the model the application authenticates against —
the starter's `database/models/user.py`, because `app/bootstrap.py` passes it
to `AuthenticationMiddleware`.

###  `user:admin` and `user:create`

```bash
$ uv run sillo user:admin ada@example.com ada
Password: ••••••••
Confirm:  ••••••••
✓ Created ada@example.com.
  Sign in at /admin/
```

The password is read from a hidden prompt. With no terminal — CI, a container
build — it comes from `SILLO_PASSWORD` instead, and with neither the command
fails and says so rather than blocking on a prompt nobody can answer.

```bash
SILLO_PASSWORD='…' uv run sillo user:admin ci@example.com ci
```

`user:admin` omits the username when you do: it defaults to the mailbox, so
`ada@example.com` becomes `ada`.

###  `user:list`

```bash
$ uv run sillo user:list
 id   email             username   admin   active
 ──   ───────────────   ────────   ─────   ──────
  1   ada@example.com   ada         yes     yes

  1 shown
```

`--staff` narrows it to accounts with admin access. `-l` limits the rows.

###  `user:active` and `user:staff`

Deactivating is the reversible alternative to deleting: credentials stop
working immediately and the rows referencing the user stay valid.

```bash
uv run sillo user:active ada@example.com --off   # cannot sign in
uv run sillo user:active ada@example.com         # can again
uv run sillo user:staff ada@example.com          # grant admin access
uv run sillo user:staff ada@example.com --revoke
```

The identifier is an email address or a username, and matches deactivated
accounts too — an account you cannot find is one you could never turn back on.

##  Processes

###  `queue:work`

```
  OPTIONS
    -q, --queue        Queue to consume. Repeatable, highest priority first
    -c, --concurrency  Jobs at once  [4]
    --timeout          Seconds one job may run  [60.0]
    --max-jobs         Restart after this many jobs. 0 is unlimited  [0]
```

```bash
QUEUE_URL=redis://localhost:6379 uv run sillo queue:work
uv run sillo queue:work --queue urgent --queue default
```

Queues are consumed in the order named, so the first is drained before the
second is looked at.

Without a `redis://` URL the queue lives in this process, so nothing a web
process dispatches ever reaches it. The command says so rather than sitting at
zero looking healthy.

###  `queue:list` and `queue:failed`

```bash
$ uv run sillo queue:list
 queue     waiting
 ───────   ───────
 default         0
```

`queue:failed` lists jobs that exhausted their retries, `queue:forget <id>`
drops one, and `queue:flush` drops them all. The failed-job record is in memory
unless you bind a durable one, and `queue:failed` reports that distinction
rather than printing "no failures" at somebody about to stop looking.

###  `schedule:run` and `schedule:list`

```bash
$ uv run sillo schedule:list
 name    trigger     status   runs   last run
 ─────   ─────────   ──────   ────   ────────
 prune   0 3 * * *   active      0   —

$ uv run sillo schedule:run
```

`schedule:pause <id>` and `schedule:resume <id>` stop and restart one task.

These need a scheduler, which `setup_scheduler(app)` puts on `app.state`. The
starter has that behind the commented-out `_register_work(application)` in
`app/bootstrap.py`; until you uncomment it, the schedule commands say there is
no scheduler bound rather than reporting an empty one.

###  `serve` and `routes`

```bash
uv run sillo serve --reload          # development
uv run sillo serve -p 9000
uv run sillo routes                  # every route, method and handler
uv run sillo routes -m post          # only POST
```

Both default to the application `sillo` already found, so neither needs an
import string.

##  Make targets

The Makefile wraps the commands typed most often. They are shorthand, not a
different mechanism.

| Target | Runs |
|---|---|
| `make migrate` | `db:init` + `db:make initial` on a fresh clone, then `db:migrate` |
| `make migration m="add_posts"` | `db:make "add_posts" --apply` |
| `make plan` | `db:plan` |
| `make rollback to=0001_initial` | `db:rollback 0001_initial` |
| `make admin e=… u=…` | `user:admin` |
| `make users` | `user:list` |
| `make dev` | `serve --reload` |
| `make worker` / `make scheduler` | `queue:work` / `schedule:run` |

`make migrate` is the one that does more than rename: on a fresh clone there is
no migration to apply yet, so it writes the first one before applying it. That
bootstrap only runs when the migrations package is empty, so a later
`make migrate` never writes one behind your back.

##  Adding your own

Register a command on the application and it appears in the same listing,
grouped by the part of its name before the colon.

```python
# app/main.py
from sillo.console import Argument, Command, Option

app = create_app()


@app.add_command
class Backfill(Command):
    """Fill in slugs for posts written before the column existed."""

    name = "posts:backfill"
    help = "Backfill post slugs"

    arguments = [
        Argument("since", default=None, help="Only posts after this date"),
        Option("batch", type=int, default=100, help="Rows per batch"),
    ]

    async def handle(self):
        from database.models.post import Post

        query = Post.filter(slug=None)
        if self.argument("since"):
            query = query.filter(created_at__gte=self.argument("since"))

        total = 0
        for post in await query.limit(self.option("batch")):
            post.slug = slugify(post.title)
            await post.save()
            total += 1

        self.success(f"Backfilled {total} posts.")
```

```bash
uv run sillo posts:backfill
uv run sillo posts:backfill 2024-01-01 --batch 500
```

For something short, the decorator form skips the class:

```python
@app.command("cache:clear", help="Drop every cached entry")
async def clear(command):
    await cache.flush()
    command.success("Cache cleared.")
```

Commands registered on the application are added last, so a name you choose
overrides a built-in one of the same name. `sillo.console` documents the
parameter types, the output helpers and the interactive prompts in full — see
[Console Commands](/guides/console/).

##  Errors and output

Exit codes are what a script would expect: `0` for success, `2` for a usage
error, `1` for a command that failed, `130` for a cancelled prompt.

```bash
$ uv run sillo db:rollback
✗ missing argument <TARGET>
  Usage: sillo db:rollback <TARGET> [options]
```

Colour is dropped when the output is not a terminal, so a log file gets plain
text. `NO_COLOR=1` turns it off everywhere and `FORCE_COLOR=1` keeps it through
a pipe.

##  Related

- [Console Commands](/guides/console/) — the toolkit underneath, in full
- [Database](/guides/start/database/) — what the migration commands act on
- [Background Work](/guides/start/background-work/) — the queue and scheduler
- [Deployment](/guides/start/deployment/) — running these in production
