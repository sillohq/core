---
title: Environment & .env
description: How Sillo reads .env files, with no python-dotenv and no setup
---

Sillo reads `.env` itself. There is no `python-dotenv` to install, no
`load_dotenv()` to remember to call, and no import order to get right.

Write a `.env`:

```bash
DATABASE_URL=postgresql://localhost/mydb
JWT_SECRET=dev-secret
DEBUG=true
```

Then read it:

```python
from sillo import SilloApp
from sillo.config import Config

class Settings(Config):
    database_url: str
    jwt_secret: str
    debug: bool = False

settings = Settings()      # .env has already been read
app = SilloApp(debug=settings.debug)
```

## When the file is read

Both `SilloApp(...)` and any `Config` subclass load the project's `.env` on
construction, once per process. The `sillo` command loads it earlier still —
before your application module is imported — so a module that reads
`os.environ` at import time sees the file's values too.

The file is found by searching upward from the working directory, stopping at
the project root (the first directory holding `pyproject.toml`, `uv.lock`,
`setup.py`, `setup.cfg` or `.git`). Running `uvicorn app:app` from
`myproject/app/handlers` finds `myproject/.env`; a stray `.env` in your home
directory is never picked up.

## Precedence

Three sources, most specific first:

1. **Arguments** — `Settings(database_url="sqlite://:memory:")`
2. **The real environment** — what the shell, container or platform exported
3. **`.env`** — the file

A variable already exported wins over the file. That is what makes the same
image work in every environment: the `.env` baked in during development is
still there, and production's exported `DATABASE_URL` overrules it.

To go the other way, load with `override=True`:

```python
from sillo.env import load_env

load_env(".env.local", override=True)   # the file wins this time
```

## The file format

```bash
# A comment. Blank lines are fine too.

DATABASE_URL=postgresql://localhost/mydb    # a trailing comment
export API_KEY=abc123                        # `export` is allowed and ignored

QUOTED="spaces   are kept"
LITERAL='nothing $expands in here'
ESCAPED="line one\nline two"

PRIVATE_KEY="""-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkq...
-----END PRIVATE KEY-----"""

DB_HOST=db.internal
DATABASE_URL=postgres://${DB_HOST}:5432/app
PORT=${PORT:-8000}
PASSWORD=pa\$\$word
```

| Form | Meaning |
|------|---------|
| `KEY=value` | Everything to the end of the line, trimmed |
| `KEY="value"` | Escapes (`\n`, `\t`, `\"`) and `${REFERENCES}` are resolved |
| `KEY='value'` | Taken literally — nothing is expanded or unescaped |
| `KEY="""…"""` | Multi-line, resolved like a double-quoted value |
| `KEY='''…'''` | Multi-line, literal |
| `export KEY=value` | The prefix is dropped |
| `# comment` | Skipped |
| `KEY=value # note` | The comment is dropped — the space before `#` is required |

Two details that bite people elsewhere:

- `PASSWORD=pa#ssword` keeps its `#`. A hash only starts a comment when
  whitespace comes before it.
- `PASSWORD=pa$$word` would expand. Write `pa\$\$word`, or single-quote the
  value, to keep the dollars.

### References

`${NAME}` and `$NAME` resolve against names defined earlier in the same file
first, then against the surrounding environment. A name that resolves nowhere
becomes the empty string.

| Form | Result |
|------|--------|
| `${NAME}` | The value, or empty |
| `${NAME:-fallback}` | `fallback` when `NAME` is unset **or empty** |
| `${NAME-fallback}` | `fallback` only when `NAME` is unset |
| `\$NAME` | A literal `$NAME` |

## Choosing a different file

Point `SILLO_ENV_FILE` at another path, and everything that loads
automatically loads that instead:

```bash
SILLO_ENV_FILE=.env.production uvicorn app:app
```

Set it to the empty string to turn automatic loading off — useful in tests,
where the environment should be the only source of truth:

```bash
SILLO_ENV_FILE= pytest
```

A single config class can name its own file:

```python
class Settings(Config):
    database_url: str

    class Env:
        env_file = ".env.production"   # or None, to load no file at all
```

## Layering files

There is no implicit `.env.local`. Two calls, in the order you want them:

```python
from sillo.env import load_env

load_env()                              # .env
load_env(".env.local", override=True)   # whatever the developer changed
```

## Reading one variable

Not everything deserves a config class. `env()` reads a single variable with
a type:

```python
from sillo.env import env

port = env("PORT", 8000, cast=int)
debug = env("DEBUG", False, cast=bool)
hosts = env("ALLOWED_HOSTS", "localhost", cast=lambda raw: raw.split(","))
secret = env("JWT_SECRET")     # no default: raises KeyError if unset
```

`cast=bool` understands what `.env` files actually contain — `true`, `yes`,
`on`, `1` and their opposites — rather than Python's rule where the string
`"false"` is true.

## The API

Everything lives in `sillo.env`:

| Function | Does |
|----------|------|
| `load_env(path=None, *, override=False, search=True)` | Reads a file into `os.environ`, returns what it applied |
| `find_env(name=".env", start=None)` | The upward search, on its own |
| `parse_env(text)` | Parses text to a dict, touching nothing |
| `env(key, default, *, cast=None)` | One typed read |
| `autoload()` | What the framework calls: find, load, remember |

A missing file is never an error. Most deployments have no `.env` at all —
the platform exports the variables — and an application should start anyway.

## Docker and deploys

Do not ship `.env` in the image. Export the variables instead:

```bash
docker run -e DATABASE_URL=postgres://... -e JWT_SECRET=... myapp
```

They win over any `.env` that ends up in the image regardless, but a secret
that is not in the image cannot leak from it.

## See Also

- [Configuration Management](/v1.0/guides/configuration/) — config classes, validation, secret masking
- [Secrets & .env](/v1.0/start/secrets/) — what `sillo-start` generates
