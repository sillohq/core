---
title: Internals
description: "How sillo-start fetches and unpacks a starter, the path-traversal guard, and using Template, fetch and personalise as a library from your own tooling."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Start Internals
  - tag: meta
    attrs:
      property: og:description
      content: Fetching, unpacking, the path-traversal guard, and using the tool as a library.
---

The CLI layer is thin: it parses arguments, calls into
`sillo_start.project.template`, and renders the result. Everything interesting
is in that module, and it is importable.

## A tarball, not a clone

The starter is downloaded from `codeload.github.com` as a gzipped tarball:

```
https://codeload.github.com/sillohq/starter/tar.gz/main
```

Three things follow:

- **No `git` is needed.** It is used only for `git init` afterwards, and
  skipped when absent.
- **No history arrives.** Nobody starts a project by deleting somebody else's
  commits.
- **A tag pins as easily as a branch.** The ref is just the last path segment.

The request has a **60 second** timeout and sends no credentials, which is why
[private repositories are not supported](/start/custom-starters/#private-repositories).

## Unpacking

GitHub wraps the archive in a single top-level directory named after the
repository and the commit. `starter-8f3a91c/`. That prefix is stripped so the
project's files land at the destination root rather than one level down.

### The path-traversal guard

Every member's resolved destination is checked against the destination root:

```python
target = (destination / relative).resolve()
if not str(target).startswith(str(destination.resolve())):
    raise CommandError(f"{template.slug} contains an unsafe path: {member.name}")
```

A member named `../../.ssh/authorized_keys` is **refused**, not sanitised.
Quietly rewriting the path would hide that an archive tried it, and the only
reason an archive contains one is that somebody put it there.

Extraction also uses `filter="data"`, which refuses absolute paths, links
pointing outside the tree, and device files.

## Using it as a library

```python
from pathlib import Path
from sillo_start.project.template import (
    DEFAULT_TEMPLATE, Template, fetch, personalise, generate_secret_key,
)
```

### `Template`

A frozen dataclass of owner, repo and ref.

```python
Template.parse("sillohq/starter")                  # ref="main"
Template.parse("sillohq/starter@v1.2")             # ref="v1.2"
Template.parse("sillohq/starter", ref="develop")   # the keyword wins
Template.parse("https://github.com/sillohq/starter.git")

template.slug     # "sillohq/starter"
template.url      # the codeload tarball URL
```

Raises `CommandError` on anything that does not resolve to `owner/repo`.

### `fetch`

```python
fetch(template, Path("./myapp"))
```

Downloads, unpacks, strips the prefix, and creates the destination if it does
not exist. Raises `CommandError` on a 404, any other HTTP status, an
unreachable host, an empty archive, or an unsafe member path.

It does not check whether the destination is empty. That is the CLI's decision,
because a library caller may well be unpacking deliberately over something.

### `personalise`

```python
changed = personalise(Path("./myapp"), "myapp", template_name="our-template")
# ['pyproject.toml', 'app/config.py', '.env.example', 'uv.lock', '.env']
```

Applies the [substitutions](/start/personalisation/#the-substitutions), updates
`uv.lock`, and writes `.env` from `.env.example` with fresh secrets. Returns
the paths it changed, relative to the root.

`template_name` is what the starter calls itself, defaulting to `starter`. This
is the parameter the CLI does not expose. A custom starter that wants the
renaming either names itself `starter` internally, or calls this directly.

Existing files are respected: `.env` is never replaced.

### `generate_secret_key`

```python
generate_secret_key()        # 50 URL-safe characters
generate_secret_key(64)      # 64
```

`secrets.token_urlsafe`, truncated to the requested length. See
[Secrets](/start/secrets/).

## Putting it together

The whole of `create-app`, without the CLI:

```python
from pathlib import Path
from sillo_start.project.template import DEFAULT_TEMPLATE, Template, fetch, personalise

template = Template.parse(DEFAULT_TEMPLATE, ref="main")
root = Path("./myapp").resolve()

fetch(template, root)
changed = personalise(root, "myapp")
print(f"renamed {len(changed)} file(s)")
```

Useful when you are generating several projects at once, or wrapping this in
tooling of your own that has its own idea of where projects go.

## Package layout

```
sillo_start/
  __main__.py            python -m sillo_start
  exceptions.py          SilloStartError and its three subclasses
  cli/
    app.py               the Typer app, global flags, error handling
    create.py            create-app
  project/
    template.py          Template, fetch, personalise, secrets
  utils/
    console.py           the output helpers
    naming.py            name conversions and validation
    pkgmanagers.py       the uv/pip and frontend adapters
    subprocess.py        run(), tool_exists()
```

Errors are handled in exactly one place (a decorator applied to every command
body) so the message rendering and the exit codes are decided once. See [Errors
and exit codes](/start/errors/#the-exception-hierarchy).

## Running it from source

```bash
git clone https://github.com/sillohq/start
cd start
uv sync --all-extras
uv run pytest
uv run sillo-start create-app myapp
```

`python -m sillo_start` works too, and is the same entry point.
