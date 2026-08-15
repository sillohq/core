---
title: Package Managers
description: "How sillo-start detects and drives uv, pip, and the frontend managers: the adapter interface, the preference order, and why an existing lockfile wins."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Package Managers in Sillo Start
  - tag: meta
    attrs:
      property: og:description
      content: "uv, pip, bun, npm, pnpm and yarn: detection, preference order, and the adapter interface."
---

Sillo Start prefers `uv`. It never *requires* one.

Each manager is a small adapter that knows how to phrase add, remove, install
and run for its own tool, so the calling code expresses intent ("install this
project's dependencies") and never branches on which tool is in use.

## Python

Two are supported:

| | `add` | `sync` | `run` |
| --- | --- | --- | --- |
| **uv** | `uv add pkg` | `uv sync` | `uv run <cmd>` |
| **pip** | `pip install pkg` | `pip install -e .` | *(none)* |

### Detection

```python
from sillo_start.utils.pkgmanagers import detect_python_manager

detect_python_manager()      # UvManager if uv is on PATH, else PipManager
```

`uv` if it is on your `PATH`, `pip` otherwise. There is no configuration and no
prompt. The preference is fixed, and the fallback always exists.

This is what `--install` uses, and what decides how the
[next steps](/start/create-app/#what-it-prints) are phrased.

### The difference that matters

`uv add` edits `pyproject.toml` and the lockfile itself. `pip install` does
not touch either.

So when pip is the manager, whatever is adding a dependency has to write the
manifest entry too, and when uv is, it must **not**, or the dependency is
recorded twice. The adapters carry that distinction rather than leaving it to
each caller to remember.

### Why not Poetry, PDM, Hatch?

They work fine with a project Sillo Start created. It produces a standard PEP
621 `pyproject.toml`, which any of them can take over.

What is not supported is Sillo Start *driving* them. Two adapters is what it
takes to cover "the fast one" and "the one that is always there", and every
further adapter is a code path that has to keep working without being the one
anybody exercises.

To use Poetry with a created project:

```bash
sillo-start create-app myapp
cd myapp
rm uv.lock
poetry install
poetry run sillo db:migrate
```

The `uv.lock` goes because it pins a resolution Poetry did not make; the
`pyproject.toml` stays exactly as it is.

## Frontend

Four are supported, for the [Inertia starter](/start/starters/) and anything
else with a `package.json`:

| | Lockfile | Install | Add |
| --- | --- | --- | --- |
| **bun** | `bun.lockb` | `bun install` | `bun add [-d]` |
| **pnpm** | `pnpm-lock.yaml` | `pnpm install` | `pnpm add [-D]` |
| **npm** | `package-lock.json` | `npm install` | `npm install [--save-dev]` |
| **yarn** | `yarn.lock` | `yarn install` | `yarn add [--dev]` |

### An existing lockfile wins

```python
from sillo_start.utils.pkgmanagers import detect_frontend_manager

detect_frontend_manager(project_dir)
```

If the directory has a lockfile, that manager is used, even if a preferred one
is also installed. A project with `pnpm-lock.yaml` keeps using pnpm on a
machine that happens to have bun.

That rule exists because the alternative is a second lockfile in the
repository, which is how two developers end up with different dependency trees
and one of them has a bug the other cannot reproduce.

With no lockfile, preference order applies: **bun, pnpm, npm, yarn**, first one
installed. With none installed it returns npm, on the reasoning that npm ships
with Node and the failure will be clear.

## The adapter interface

Both hierarchies are small and public, so a project can use them for its own
tooling:

```python
from pathlib import Path
from sillo_start.utils.pkgmanagers import python_manager, frontend_manager

uv = python_manager("uv")
uv.available()                                   # is it installed?
uv.add_command(["httpx"], group="dev")           # ['uv', 'add', 'httpx', '--group', 'dev']
uv.add(["httpx"], cwd=Path("."), group="dev")    # build it and run it

bun = frontend_manager("bun")
bun.run_command("build")                         # ['bun', 'run', 'build']
```

Every adapter has both a `*_command` method that **builds** the argument list
and a method that **runs** it. The split is what makes the whole thing testable
without a subprocess: a test asserts on the command, and only integration tests
actually execute one.

An unknown name raises `ToolNotFoundError` and lists the ones it knows:

```
Unknown Python package manager 'poetry'. Known: pip, uv.
```

## Failures are never swallowed

When `--install` fails, the manager's own output is printed and the exit code
is `1`:

```
✗ uv exited with code 1.
  × No solution found when resolving dependencies:
  ╰─▶ Because myapp depends on sillo-framework>=9.0 …
```

The resolver's message is the useful one. Reprinting it beats replacing it with
"installation failed", and the project is still on disk either way. Fix the
cause and install by hand.

## See also

- [Installing Sillo Start](/start/install/): installing the tool itself.
- [After creating](/start/after-creating/): the install step in context.
