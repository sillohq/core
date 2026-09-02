---
title: Personalisation
description: "What sillo-start rewrites when it renames a starter to your project: the exact substitutions, the lockfile, and the files it deliberately leaves alone."
head:
  - tag: meta
    attrs:
      property: og:title
      content: How Sillo Start Personalises a Project
  - tag: meta
    attrs:
      property: og:description
      content: The exact substitutions made when a starter becomes your project, and what is deliberately left alone.
---

The starter calls itself `starter`. Your project does not. Personalisation is
the step between.

```
✓ Fetched sillohq/starter and renamed 3 file(s)
```

## Targeted, not find-and-replace

Every substitution is a **named file and an exact string**. Nothing is a
blanket search across the tree.

That matters more than it sounds. A starter's README says "starter" in prose
several times, a Makefile comment mentions it, a docstring explains what the
starter is for. A find-and-replace turns all of those into sentences about
`myapp` that no longer parse as English. Naming each substitution means prose
is left as written.

## The substitutions

For a project named `myapp`:

| File | From | To |
| --- | --- | --- |
| `pyproject.toml` | `name = "starter"` | `name = "myapp"` |
| `app/config.py` | `"""Typed settings for Starter."""` | `"""Typed settings for Myapp."""` |
| `app/config.py` | `app_name: str = "Starter"` | `app_name: str = "Myapp"` |
| `app/config.py` | `sqlite://storage/starter.db` | `sqlite://storage/myapp.db` |
| `.env.example` | `# Starter environment.` | `# Myapp environment.` |
| `.env.example` | `APP_NAME=Starter` | `APP_NAME=Myapp` |
| `.env.example` | `sqlite://storage/starter.db` | `sqlite://storage/myapp.db` |

Two capitalisations are used. `myapp` is the name as you typed it; `Myapp` is
its title-cased form with separators removed. `my-cool-app` becomes
`MyCoolApp`.

A file that is not there, or a string that is not in it, is skipped rather than
being an error. That is what lets a custom starter share some of these
conventions without having to adopt all of them.

The count reported at the end is the number of *files* changed, not
substitutions.

## The lockfile

`uv.lock` gets one more: the project names itself as a member of its own
workspace, so the lockfile has to agree with `pyproject.toml` or `uv sync`
fails on a renamed project.

```
name = "starter"   →   name = "myapp"
```

This one is a plain replacement across the file, because in a lockfile that
string only ever means the package name.

## What is deliberately not rewritten

### Model files

Model modules are absent from the list, on purpose.

A model's docstring becomes its `table_description` in the generated schema. So
rewriting one puts your models out of step with the migration the starter
committed, and the next `sillo db:make` notices the difference and writes a
spurious second migration describing a comment change.

The cost of leaving them is a docstring that says "starter". The cost of
rewriting them is a migration nobody asked for on the first day of the project.

### Prose

READMEs, comments, docstrings outside the list above. See
[Targeted, not find-and-replace](#targeted-not-find-and-replace).

### An existing `.env`

Never touched. It may hold real credentials. See
[Secrets and `.env`](/v1.0/start/secrets/).

### Anything under `.git`

Not applicable in the normal case (the starter arrives as a tarball with no
history) but worth stating for `--force` into an existing checkout.

## Doing it yourself

`personalise` is a plain function, and it takes the starter's own name so it
can be pointed at a custom one:

```python
from pathlib import Path
from sillo_start.project.template import personalise

changed = personalise(Path("./myapp"), "myapp", template_name="our-template")
```

It returns the list of paths it changed, relative to the root. See
[Internals](/v1.0/start/internals/).

## If you need more

Personalisation is deliberately small. Anything beyond renaming (choosing a
database driver, dropping a subsystem, adding a frontend) belongs in the
starter itself, as something the application already supports and you
configure, rather than as a substitution the scaffolder performs.

That is the same reasoning as [fetching a repository rather than rendering
templates](/v1.0/start/#a-starter-repository-not-a-generator): options a generator
offers are options nobody ever ran together.
