---
title: Secrets and .env
description: "How a new Sillo project gets its own signing keys — which variables are regenerated, how the keys are produced, and why an existing .env is never replaced."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Secrets and .env in a New Sillo Project
  - tag: meta
    attrs:
      property: og:description
      content: Fresh signing keys per project, and the rules around an existing .env.
---

Every project created by `sillo-start` gets its own secrets. No two share a
signing key.

## What happens

`.env` is created from `.env.example`, line for line, with three variables
replaced by freshly generated values:

- `SECRET_KEY`
- `JWT_SECRET`
- `APP_KEY`

Everything else is copied unchanged, comments included.

```bash
# .env.example (committed)
SECRET_KEY=generate-me

# .env (created, gitignored)
SECRET_KEY=xQ8mF2vK9pR4tW7nL3jH6bY1cZ5dA0sE8gU2iO4wT6rN9kM3
```

## Why this is not optional

A secret committed to a starter repository is a placeholder by definition — it
is on GitHub, in every clone, and in every fork. A project that shipped with it
would be signing its sessions with a published key, and anyone could mint a
valid session cookie for it.

Generating one per project makes that failure impossible rather than
documented. There is no step to forget.

## How the keys are generated

`secrets.token_urlsafe`, truncated to 50 characters:

```python
from sillo_start.project.template import generate_secret_key

generate_secret_key()        # 50 characters
generate_secret_key(64)      # 64
```

`secrets` is the standard library's cryptographically secure generator — not
`random`, which is seeded predictably and is the classic way a "random" token
turns out to be guessable.

URL-safe base64 means the value is safe in a `.env` file, a shell, a URL and a
header without escaping.

## An existing `.env` is never replaced

If `.env` already exists, nothing is written and nothing is reported as
changed.

That file may hold real credentials — a database password, an API key from a
service you already configured. Overwriting it because a scaffolding tool ran
in the wrong directory would be an unrecoverable loss, and no amount of "are
you sure?" makes that a good default.

The same applies with `--force` into a non-empty directory. `--force` allows
the *directory*; it does not extend to your secrets.

## If there is no `.env.example`

Nothing is created. A starter that does not ship one is assumed not to want an
environment file, and inventing one would be guessing at variables it never
reads.

## What to do next

The generated `.env` is for local development. Each deployed environment needs
its own:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set it through your platform's environment configuration rather than by
shipping a file. `.env` is gitignored in the starter, and should stay that way.

:::caution[Rotating a key signs everyone out]
`SECRET_KEY` signs session cookies. Changing it in a running environment
invalidates every existing session at once — which is exactly what you want
after a leak, and exactly what you do not want by accident during a routine
deploy.

Rotate it deliberately, and tell people it is going to happen.
:::

## Adding your own

To have another variable generated for a custom starter, name it one of the
three above — the list is fixed. Anything else is copied from `.env.example` as
written, which is the right behaviour for a value that is configuration rather
than a secret.

For a secret with a different name, the honest options are to rename it to one
of the three, or to generate it in the project's own first-run step where the
project can decide what a good value looks like.

## See also

- [Configuration](/guides/configuration/) — how the application reads these.
- [Personalisation](/start/personalisation/) — the other half of what happens
  after a fetch.
