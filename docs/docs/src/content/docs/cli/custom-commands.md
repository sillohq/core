---
title: Writing Commands
description: "Adding your own commands to the sillo CLI: the Command class, the handle method, registration on the application, the context hook, and exit codes."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Writing Sillo Console Commands
  - tag: meta
    attrs:
      property: og:description
      content: The Command class, handle(), registration, the context hook and exit codes.
---

Your commands go on the same `sillo` command as the framework's. There is no
second entry point and no `manage.py`.

## A command

```python
# app/commands.py
from sillo.console import Argument, Command, Flag


class Backfill(Command):
    name = "posts:backfill"
    help = "Fill in slugs for posts that have none"

    arguments = [
        Argument("limit", type=int, default=100, help="How many to process"),
        Flag("dry-run", help="Report what would change, and change nothing"),
    ]

    async def handle(self):
        from app.models import Post

        posts = await Post.filter(slug="").limit(self.argument("limit"))
        if not posts:
            self.muted("Nothing to backfill.")
            return

        for post in posts:
            self.bullet(f"{post.id} → {slugify(post.title)}")
            if not self.flag("dry_run"):
                post.slug = slugify(post.title)
                await post.save()

        verb = "Would update" if self.flag("dry_run") else "Updated"
        self.success(f"{verb} {len(posts)} posts.")
```

## Registering it

On the application, which is where `sillo` looks:

```python
# app/main.py
from sillo import SilloApp
from app.commands import Backfill

app = SilloApp(...)
app.add_command(Backfill)
```

That is all. `sillo posts:backfill --help` now works.

```bash
sillo posts:backfill --dry-run
sillo posts:backfill 500
```

### Your names win

Project commands are registered **last**, with override enabled. If you name a
command `db:migrate`, yours replaces the bundled one. That is intentional: a
project that needs its migration command to also rebuild a search index should
be able to say so, and the alternative (a name collision that is an error)
would mean the framework's names were reserved forever.

## The four attributes

| Attribute | Purpose |
| --- | --- |
| `name` | How the command is invoked. A colon groups it in the help. |
| `help` | The one line in the listing. Falls back to the docstring's first line. |
| `description` | The longer text in `--help`. Falls back to the whole docstring. |
| `aliases` | Other names that dispatch here. |
| `hidden` | Keep it out of the listing. It still runs. |

Grouping is by name, not configuration. `posts:backfill` appears under a
`POSTS` heading because of the colon.

`hidden` is for the commands that exist but should not be advertised, a
destructive repair tool, or something only CI calls.

## Reading parameters

Three accessors, one per kind:

```python
self.argument("limit")   # positional
self.option("format")    # --format json
self.flag("dry_run")     # --dry-run
```

They are separate on purpose. Asking for a flag with `self.option()` raises and
tells you which accessor to use, rather than returning a value of a shape you
did not expect:

```
KeyError: 'dry_run' is declared as flag, not option; read it with .flag('dry_run')
```

Dashes and underscores are interchangeable in lookups, so a parameter declared
`Flag("dry-run")` reads as `self.flag("dry_run")` or `self.flag("dry-run")`,
whichever fits the call site.

Anything after `--` is available as `self.extra`, unparsed.

See [Arguments, options and flags](/cli/arguments/) for the full declaration
surface.

## Sync or async

`handle` may be either:

```python
async def handle(self):   # runs on the console's event loop
def handle(self):         # runs with no loop in this thread
```

Use `async def` unless your command hands the loop to something else. The
console notices the difference and does not create a loop for synchronous
commands.

## The `context` hook

Override `context()` to open something around every command in a family, a
database connection being the usual one:

```python
class DatabaseCommand(Command):
    def context(self):
        return database()          # an async context manager


class Backfill(DatabaseCommand):
    name = "posts:backfill"
    ...
```

The console enters it before `handle` and exits it after, whether `handle`
returned or raised. Returning `None` runs `handle` directly.

You rarely need this in a project command run through `sillo`: the application
was imported to find the command in the first place, so its database is already
set up. It matters for a [console of your own](/cli/standalone-consoles/),
where nothing has initialised the ORM yet.

## Failing

```python
user = await find(identifier)
if user is None:
    self.fail(f"No user matches {identifier!r}.")

# everything below here can treat `user` as found
```

`fail()` always raises, and is annotated `NoReturn` so type checkers know it.
That is what lets you write the guard above without a `return` a reader would
have to think about.

For a different exit code:

```python
self.fail("Refusing to run against production.", exit_code=3)
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success. `handle` returned `None`, or `0`. |
| `2` | A usage error: an unknown option, a missing argument, a bad value. |
| `130` | Ctrl-C, at a prompt or during work. |
| *n* | Whatever `self.fail(..., exit_code=n)` or `return n` asked for. |

Returning an `int` from `handle` sets the code directly, which is the tidy way
to report "asked, and the answer was no":

```python
if not self.confirm("Drop every recorded failure?"):
    self.muted("Nothing done.")
    return 1
```

## One-liners

For commands not worth a class, a project console can register a function. See
[Building a console](/cli/standalone-consoles/#function-form). The class form
is the primary one and is what anything with a real body should use.

## See also

- [Arguments, options and flags](/cli/arguments/)
- [Output](/cli/output/): tables, pairs, panels, progress bars.
- [Prompts](/cli/prompts/): asking questions safely.
