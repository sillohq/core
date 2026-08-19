---
title: create-app
description: "The sillo-start create-app command in full: argument forms, every flag, what it prints, and the order in which it fetches, renames, initialises git and installs."
head:
  - tag: meta
    attrs:
      property: og:title
      content: sillo-start create-app
  - tag: meta
    attrs:
      property: og:description
      content: Every argument and flag of the command that creates a Sillo project.
---

```bash
sillo-start create-app myapp
```

The tool has one command. This is it.

## Argument forms

```bash
sillo-start create-app myapp                        # the default starter
sillo-start create-app sillohq/starter myapp        # named explicitly
sillo-start create-app sillohq/starter@v1.2 myapp   # pinned to a tag
sillo-start create-app acme/our-template myapp      # your own starter
```

With **one** argument it is the project name, and the default starter
(`sillohq/starter`) is used. With **two** the first is the starter and the
second is the name.

That asymmetry is the point: `create-app myapp` does the obvious thing, and you
only name a starter when you actually mean a different one.

A full GitHub URL works too, so pasting what is in your address bar does what
you expect:

```bash
sillo-start create-app https://github.com/sillohq/starter myapp
```

Trailing `.git` and a `www.` prefix are both stripped.

## Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `--ref <branch\|tag>` | `main` | Which revision to take |
| `-d`, `--directory <path>` | `./<name>` | Where to create the project |
| `--install` / `--no-install` | off | Install dependencies after fetching |
| `--git` / `--no-git` | on | Initialise a git repository |
| `--force` | off | Allow a directory that is not empty |

Plus the [global flags](/start/install/#global-flags): `-v`, `-q`, `-h`.

### `--ref`

Takes precedence over an `@ref` in the starter argument, so these are the same
thing and the flag wins when both are given:

```bash
sillo-start create-app sillohq/starter@v1.2 myapp
sillo-start create-app sillohq/starter myapp --ref v1.2
```

Any branch or tag a public repository has. See
[Custom starters](/start/custom-starters/#pinning-a-revision).

### `-d`, `--directory`

```bash
sillo-start create-app myapp --directory ~/code/myapp
sillo-start create-app myapp -d .
```

Where to put the files. The project is still *called* `myapp`. The directory
and the name are separate, which is what lets you create a project into a
repository you have already cloned.

### `--install`

Off by default, so creating a project takes a second rather than a minute.

With it, dependencies are installed straight away using whichever
[package manager](/start/package-managers/) is available:

```bash
sillo-start create-app myapp --install
```

A failing install is reported with the manager's own output and exits `1`. The
project is still on disk, and you can fix the cause and install by hand. The
output is never swallowed.

### `--no-git`

A git repository is initialised by default. `--no-git` skips it.

It is also skipped automatically when `git` is not installed, or when the
directory is already a repository, creating a project inside an existing
checkout does not reinitialise it.

Note what this does *not* do: no commit is made. The files are there for you to
look at, and the first commit is yours.

### `--force`

A directory that is not empty is refused:

```
✗ /Users/you/code/myapp is not empty.
  Choose another directory, or pass --force.
```

`--force` allows it. Existing files are left in place; the starter's files are
written alongside them, overwriting on a name collision.

## What it prints

```
Creating myapp
from sillohq/starter@main

  › Fetching sillohq/starter…
✓ Fetched sillohq/starter and renamed 3 file(s)

Next steps
  cd myapp
  uv sync
  uv run sillo db:migrate
  uv run uvicorn app:app --reload

  The starter's README covers configuration, migrations and deployment.
```

The next steps are phrased for the tooling you actually have: `uv` when it is
on your `PATH`, plain `pip` and a bare `sillo` when it is not. Printing
`uv run …` at someone without `uv` would be printing a command that cannot
work.

With `--install` the install step is dropped from the list, since it has
already happened.

## The order of operations

1. **Validate the name.** Before anything is fetched: it becomes both a
   directory and a Python package, so an unusable name is worth refusing early.
   See [Project names](/start/naming/).
2. **Parse the starter.** `owner/repo`, `owner/repo@ref` or a URL.
3. **Check the destination.** Non-empty is refused without `--force`.
4. **Fetch and unpack** the tarball.
5. **Personalise**: rewrite the name into the files that carry it, and create
   `.env` with fresh secrets. See [Personalisation](/start/personalisation/).
6. **`git init`**, unless skipped.
7. **Install**, if `--install` was given.

Steps 1 to 3 all happen before a byte is downloaded. A run that is going to
fail on your input fails immediately rather than after a download.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Created |
| `1` | Something failed: a fetch, an install |
| `2` | A usage error: a bad name, a non-empty directory, an unparseable starter |
| `130` | Ctrl-C |

See [Errors and exit codes](/start/errors/).
