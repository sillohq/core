---
title: Finding Your Application
description: "How the sillo command locates your SilloApp — SILLO_APP, [tool.sillo] app, and the conventional paths — and how to diagnose it when the wrong one is found."
head:
  - tag: meta
    attrs:
      property: og:title
      content: How the Sillo CLI Finds Your Application
  - tag: meta
    attrs:
      property: og:description
      content: SILLO_APP, [tool.sillo] app, and the conventional module paths, in the order they are tried.
---

Every project-aware command exists because `sillo` imported your application
and looked at it. That import is the one thing that has to work.

## The order

1. **`SILLO_APP`**, as a `module:attribute` import string.
2. **`[tool.sillo] app`** in the working directory's `pyproject.toml`.
3. **The conventional paths**, tried in order: `app.main:app`, `main:app`,
   `app:app`.

The first that resolves wins. The working directory is put on `sys.path` before
any of them is tried — a console script starts with its own `bin` directory on
the path, so without that step none of a project's own packages would import.

## Pointing at it explicitly

In `pyproject.toml`, which is the durable form:

```toml
[tool.sillo]
app = "app.main:app"
```

Or per invocation, which is how you point at a second application without
editing anything:

```bash
SILLO_APP=app.worker:app sillo routes
```

Both take a `module:attribute` string. A string without a colon is rejected
with the spelling it should have had, rather than being guessed at.

## When nothing is found

Running `sillo` outside a project is not an error. None of the three resolve,
the framework commands are all that is offered, and nothing is printed about
it — being in an ordinary directory is not a problem to report.

Being *pointed at* an application that then fails is different. That is a
configuration you wrote and that did not work, so it is reported:

```
warning: app.main:app could not be loaded: Could not import 'app.main': No module named 'app'
```

The framework commands still run. That is deliberate: `sillo version` is often
exactly what someone runs to find out why the rest is missing, and it would be
unhelpful for a broken import to take it down too.

The same applies one step later. If the application imports but building its
commands raises, you get the framework commands and a warning naming the
failure — not a traceback in place of a CLI.

## Diagnosing it

`sillo routes` is the quickest check that the right application was found: it
prints the routes of whatever was imported.

```bash
sillo routes
```

If that lists routes you do not recognise, one of the conventional paths
matched something you did not intend — a stray `main.py` at the repository
root, most often. Set `[tool.sillo] app` and the guessing stops.

To bypass discovery entirely for one command, `serve` and `routes` both take
the import string as their first argument:

```bash
sillo routes app.worker:app
```

## Why the application, and not a config file

What a project gets is decided by what it set up, not by configuration
repeating it somewhere else. A database manager on `app.state` means migrations
and accounts are available; a scheduler means the schedule commands are. You
wire the application once — for the application's sake — and the console
follows from it.

The cost is that the console is only as reachable as the import. That is the
trade, and it is why the failure paths above take pains to stay useful.
