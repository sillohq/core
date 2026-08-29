---
title: Custom Starters
description: "Using any GitHub repository as a Sillo starter, pinning to a branch or tag, and what makes a repository work well as one, including the conventions personalisation looks for."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Custom Sillo Starters
  - tag: meta
    attrs:
      property: og:description
      content: Use any public GitHub repository as a starter, and build one that personalises cleanly.
---

Any public GitHub repository can be a starter.

```bash
sillo-start create-app acme/our-template myapp
```

There is nothing to register and no manifest to write. A starter is a
repository; `sillo-start` fetches it and renames what it recognises.

## Accepted forms

```bash
acme/our-template
acme/our-template@v2
https://github.com/acme/our-template
https://github.com/acme/our-template.git
www.github.com/acme/our-template
```

All of them parse to the same owner and repository. A `www.` prefix, the
`https://` scheme and a trailing `.git` are stripped, and trailing slashes are
ignored, so pasting a browser URL or a clone URL both work.

Anything that does not resolve to exactly two path segments is refused:

```
✗ 'acme/team/template' is not a repository.
  Use owner/repo, for example sillohq/starter.
```

## Pinning a revision

```bash
sillo-start create-app acme/our-template@v2 myapp
sillo-start create-app acme/our-template myapp --ref v2
sillo-start create-app acme/our-template myapp --ref develop
```

Any branch or tag. Defaults to `main`. `--ref` wins when both forms are given.

Pin in CI and in team instructions. `main` is right for a person starting
something new and wrong for a script that should produce the same thing next
month.

## Private repositories

Not supported. The tarball is fetched from `codeload.github.com` with no
authentication, which is what lets the tool have two dependencies and no
credential handling.

For a private starter, clone it and copy:

```bash
git clone --depth 1 git@github.com:acme/private-template.git myapp
cd myapp && rm -rf .git && git init
```

You lose the renaming and the secret generation; do those by hand, or run
`personalise` yourself. See [Internals](/v1.0/start/internals/).

## Building one

A starter is just an application. Nothing is required. But a few conventions
make personalisation work, and they cost nothing to adopt.

### Name yourself `starter`

`personalise` takes the starter's own name as a parameter and defaults to
`starter`. From the command line there is no way to change that default, so a
repository that calls itself `starter` internally gets the renaming for free,
whatever the repository itself is called.

That is why `sillohq/starter-inertia` still names its package `starter`.

### Put the recognised strings where they are looked for

The [substitution table](/v1.0/start/personalisation/#the-substitutions) is exact,
and skips anything it does not find. Adopt the ones you want:

```toml
# pyproject.toml
name = "starter"
```

```python
# app/config.py
"""Typed settings for Starter."""

app_name: str = "Starter"
# ...
"sqlite://storage/starter.db"
```

```bash
# .env.example
# Starter environment.
APP_NAME=Starter
DATABASE_URL=sqlite://storage/starter.db
```

### Ship a `.env.example`

It is what `.env` is generated from. Name your signing keys `SECRET_KEY`,
`JWT_SECRET` or `APP_KEY` and each gets a freshly generated value. See
[Secrets](/v1.0/start/secrets/).

Anything else is copied verbatim, which is correct for configuration and wrong
for a secret. Do not commit a real one under another name expecting it to be
replaced.

### Keep migrations committed, and models unrewritten

Personalisation deliberately leaves model files alone, because a model
docstring becomes its `table_description` and rewriting one makes the models
disagree with the committed migration. Commit your initial migration and let
the docstrings say whatever they say.

### Give it CI that boots

This is the part that makes a starter worth more than a template. A workflow
that starts the application and calls its routes is what catches middleware
ordering, a missing static mount, an auth backend reading the wrong claim, none
of which a render check would notice.

The official starters do exactly this on every push, across three Python
versions.

### Keep the history out of the way

The tarball has no history, so whoever creates a project from your starter
begins with a clean slate and no commits of yours to delete. Nothing to do
here, just worth knowing that is what they get.

## Testing your starter

```bash
sillo-start create-app acme/our-template testapp --ref my-branch
cd testapp && uv sync && uv run sillo db:migrate && uv run pytest
```

Run it against a branch before tagging. The failure mode of a broken starter is
that it fails for someone else on their first day, which is the worst possible
time.
