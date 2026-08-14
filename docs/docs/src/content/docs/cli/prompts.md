---
title: Prompts
description: "Asking questions from a command — text, hidden secrets, confirmation, single and multiple choice, destructive confirmation — and how each behaves without a terminal."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Console Prompts
  - tag: meta
    attrs:
      property: og:description
      content: ask, secret, confirm, choice, multichoice and confirm_destructive.
---

Six prompts, all available on the command.

```python
name = self.ask("Project name", default="myapp")
password = self.secret("Password", confirm=True)
if self.confirm("Continue?", default=True):
    ...
```

## The rule that matters most

A prompt that cannot be shown — no terminal, a pipe, CI — **falls back to its
default**. A prompt that cannot be shown *and has no default* **raises**.

That is deliberate, and it is the difference between a scripted invocation that
stops and one that silently creates the wrong account. Guessing on the user's
behalf is never the safe option.

The practical consequence: pass `default=` to every prompt a command might hit
in CI, and the same command works in both places.

## `ask`

```python
self.ask("Project name")
self.ask("Project name", default="myapp")
self.ask("Port", validate=positive_int)
```

Free text. `validate` is any callable — return the converted value, or raise
`ValueError` with a message the user should see:

```python
def positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise ValueError("must be greater than zero")
    return value
```

The question is re-asked until the validator is happy or the user cancels.

## `secret`

```python
password = self.secret()                       # "Password"
password = self.secret("New password", confirm=True)
```

Reads without echoing. With `confirm=True` it asks twice and requires a match,
re-asking on a mismatch.

:::caution[Never take a password as an argument]
A password in `argv` is in your shell history, in `ps` output, and in any log
that records command lines. None of the framework's own commands accept one.

For non-interactive use, read it from the environment — which is what the
bundled `user:*` commands do with `SILLO_PASSWORD`:

```python
password = os.environ.get("SILLO_PASSWORD")
if not password:
    if not self.prompt.interactive:
        self.fail("No terminal to read a password from. Set SILLO_PASSWORD instead.")
    password = self.secret(confirm=True)
```
:::

## `confirm`

```python
if not self.confirm("Drop every recorded failure?", default=False):
    self.muted("Nothing done.")
    return 1
```

Yes or no. The default is what a bare Enter means, and what a non-interactive
run gets — so `default=False` on anything destructive.

## `choice`

```python
driver = self.choice(
    "Which database?",
    ["sqlite", "postgres", "mysql"],
)
```

One from a list. Arrow keys move, Enter selects. Options are either plain
strings, used as both value and label, or `(value, label)` pairs when the two
should differ:

```python
driver = self.choice("Which database?", [
    ("aiosqlite", "SQLite — no server to run"),
    ("asyncpg", "PostgreSQL"),
    ("asyncmy", "MySQL / MariaDB"),
])
```

`default=` sets the initially highlighted value, and is what a non-interactive
run returns.

## `multichoice`

```python
extras = self.multichoice(
    "Which features?",
    ["record", "cache", "jwt", "templating"],
    defaults=["record"],
    minimum=1,
)
```

Several from a list. Space toggles, Enter accepts. `minimum` refuses to accept
fewer than that many, which is how you make "at least one" a rule rather than a
hint. Returns a list.

## `confirm_destructive`

```python
agreed = self.prompt.confirm_destructive(
    "This unapplies every migration and drops the tables they made.",
    "zero",
)
```

Requires the user to type a phrase back. For operations where a mistyped `y` is
expensive — dropping a database, rolling back to zero — so that muscle memory
cannot approve them.

It is on `self.prompt` rather than the command, because it is rare enough that
it should read as a deliberate escalation.

Non-interactively it returns `False`. There is no default that could be
correct: a destructive operation that proceeds because nobody was there to stop
it is exactly what this exists to prevent. Give the command a `--force` flag for
scripts, the way `db:rollback` and `queue:flush` do.

## Cancelling

Ctrl-C at any prompt raises `Abort`, which the console reports as `Cancelled.`
and exits `130`. `Abort` is a separate exception from `KeyboardInterrupt` so a
command can catch an abandoned prompt without also catching a Ctrl-C aimed at
its own work.

## Testing commands that prompt

Force interactivity off, and every prompt takes its default:

```python
console = Console(prog="tools.py", interactive=False)
assert console.run(["posts:backfill"]) == 0
```

For a prompt with no default this raises, which is the behaviour you want a
test to catch: it means the command cannot run unattended.
