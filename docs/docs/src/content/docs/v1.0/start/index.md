---
title: Sillo Start
description: "The tool that creates a Sillo application from a starter repository. What it does, why it fetches a real application rather than rendering templates, and what it deliberately leaves alone."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Start
  - tag: meta
    attrs:
      property: og:description
      content: Create a Sillo application from a real, tested starter repository.
---

`sillo-start` creates a Sillo application. It is a separate tool from the
framework, installed once and used whenever you begin something new.

```bash
sillo-start create-app myapp
cd myapp
```

That is the whole tool. It fetches a real, working application, renames it to
yours, gives it its own secrets, and gets out of the way.

## A starter repository, not a generator

A generator renders templates. Templates are checked for *rendering*, which is
not the same as working. A project can produce valid Python, import cleanly,
render every page, and still fail on its first real request. Middleware
registered in the wrong order, an auth backend reading the wrong claim, a
missing static mount: all of them render perfectly.

[`sillohq/starter`](https://github.com/sillohq/starter) is a real application
with its own CI. Every push boots it and exercises every route, on three Python
versions. What arrives has been run, not merely written.

Three things follow from that choice:

- **The starter can be read, forked and improved on its own.** It is an
  application, not a template with holes in it.
- **A bug in what you get is fixed by releasing the starter**, not by releasing
  this tool.
- **Nothing in a created project depends on `sillo-start`.** You can delete the
  tool the moment your project exists, and the project will not notice.

## What it does not do

Migrations, creating users, running a worker, starting a server, none of it.

Those are the [`sillo` command](/v1.0/cli/), which the project has as soon as its
dependencies are installed. The split is deliberate: a scaffolding tool that
also runs your application becomes something you can never remove.

Creating a project is the one thing `sillo` does not do, for the same reason in
reverse. The framework would have to carry a copy of a starter it would then
have to keep in step with.

## The manual

| | |
| --- | --- |
| [Installing](/v1.0/start/install/) | Getting the tool, with and without `uv` |
| [`create-app`](/v1.0/start/create-app/) | Every argument and flag |
| [The starters](/v1.0/start/starters/) | What `sillohq/starter` and `starter-inertia` ship |
| [Project names](/v1.0/start/naming/) | The rules, and the name shapes derived from yours |
| [Personalisation](/v1.0/start/personalisation/) | What is rewritten, and what is left alone |
| [Secrets and `.env`](/v1.0/start/secrets/) | How a new project gets its own keys |
| [After creating](/v1.0/start/after-creating/) | Installing, migrating, first run |
| [Custom starters](/v1.0/start/custom-starters/) | Using and building your own |
| [Package managers](/v1.0/start/package-managers/) | uv, pip, and the frontend ones |
| [Errors and exit codes](/v1.0/start/errors/) | What each failure means |
| [Internals](/v1.0/start/internals/) | Fetching, unpacking, and using it as a library |

:::tip[New to Sillo?]
The starter is a complete application (auth, migrations, a queue) and it is a
lot to meet at once. If you have not written a Sillo route
yet, [Installation](/v1.0/guides/installation/) builds a single-file application
from nothing in about a minute.

Come back here when you want the wiring rather than the framework.
:::

## Requirements

Python 3.11 or newer, and network access to GitHub. The tool itself depends on
`typer` and `rich` and nothing else.

`git` is optional. The starter is fetched as a tarball, not cloned. It is used
only to run `git init` in the new project, and skipped when it is not
installed.
