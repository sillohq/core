---
title: Testing
description: The pytest suite, the smoke test that boots the application and calls every route, and why a project needs both.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Testing a Sillo Project
  - tag: meta
    attrs:
      property: og:description
      content: The pytest suite, the smoke test, and why a project needs both.
---

#  Testing

```bash
make test     # the pytest suite
make smoke    # boot the application and call every route
make check    # lint, tests, smoke — everything CI runs
```

Two kinds of test, doing different jobs. The reason for the second one is
the interesting part of this page.

##  The suite

`tests/conftest.py` gives every test its own throwaway database and a
fresh application:

```python
@pytest.fixture(autouse=True)
def _isolated_database(tmp_path, monkeypatch):
    """Point every test at its own throwaway SQLite file."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite://{tmp_path / 'test.db'}")
    yield


@pytest.fixture
def app():
    from app.bootstrap import create_app

    return create_app()


@pytest.fixture
def client(app):
    from sillo.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
```

Three things worth noticing.

**The environment variable is set before `app.config` is imported.** The
application factory imports config at call time, so the test database is
picked up rather than the development one. Set it later and you will be
testing against `storage/myapp.db`.

**`create_app()` is called per test**, so no state leaks between them.
That is why `app/main.py` is a one-liner — a module that builds the app
*and* does other work at import cannot be constructed twice.

**`TestClient` is used as a context manager.** Entering it runs the ASGI
lifespan, which is what opens the database connection and starts anything
registered on startup. Without the `with`, your handlers run against an
uninitialised ORM.

###  Writing a test

```python
def test_health_endpoint_reports_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

```python
def test_registration_rejects_a_duplicate_email(client):
    payload = {"email": "ada@example.com", "username": "ada", "password": "Hunter2!pass"}

    assert client.post("/api/auth/register", json=payload).status_code == 201
    second = client.post("/api/auth/register", json={**payload, "username": "ada2"})

    assert second.status_code == 409
```

###  Tests that need rows

The test database starts empty, and `db_generate_schemas` is off in
development but **on** for tests — the fixture points at a fresh file and
lets the ORM create the tables, because running migrations per test would
dominate the runtime.

Creating a row from outside the application needs its own connection,
because the application's belongs to the startup task:

```python
from database.config import database
from database.models.user import User


async def make_user(email="ada@example.com"):
    async with database():
        return await User.objects.create_user(
            email=email, username="ada", password="Hunter2!pass"
        )
```

Inside a `TestClient` block, the application's own loop is available
through the portal:

```python
def test_something(client):
    async def seed():
        await User.objects.create_user(...)

    client.portal.call(seed)
```

For a row that must exist *before* the first request — an administrator
the test then signs in as — a startup hook is simplest, since connections
are held in a task-scoped context:

```python
async def seed():
    user = Account(email=ADMIN_EMAIL, username="boss", is_active=True, is_staff=True)
    user.set_password(ADMIN_PASSWORD)
    await user.save()

app.on_startup(seed)
```

##  The smoke test

```bash
make smoke
uv run python scripts/smoke.py
```

```text
  ok    GET /                              200
  ok    GET /static/css/app.css            200
  ok    GET /docs                          200
  ok    GET /api/health                    200
  ok    GET /admin/login/                  200
  ok    welcome page renders               True
  ok    POST /api/auth/register            201
  ok    POST /api/auth/login               200
  ok    POST /api/auth/login, bad password 401
  ok    POST /admin/login/                 302
  ok    GET /admin/ signed in              200
  ok    GET /admin/adminactivity/          200
  ok    the sign-in was recorded           True

all checks passed
```

It boots the real application through its lifespan and calls every route.
Exit code 0 or 1, so CI and `make check` can gate on it.

###  Why it exists

A project can import cleanly, render every template, pass its unit tests
and still fail on the first real request. These are the failures it was
written for, each of them real:

- **middleware ordering** — authentication registered outside the session
  it reads from, so every admin page 500s
- **a missing static mount** — every stylesheet 404s in production and
  nowhere else
- **an auth backend reading the wrong claim** — every authenticated
  request silently loads no user
- **a queue that accepts jobs and never runs them**

None of those is visible in a template, and a unit test of a handler does
not exercise them. They need something to actually call the application.

###  Adding a check

```python
def check(label: str, actual, expected) -> None:
    ok = actual == expected
    print(f"  {'ok  ' if ok else 'FAIL'}  {label:34s} {actual}")
    if not ok:
        failures.append(f"{label}: expected {expected}, got {actual}")
```

```python
check("GET /api/posts", (await client.get("/api/posts")).status_code, 200)
```

Add one whenever you add a route. The whole file is about ninety lines and
worth reading before extending.

###  Check the effect, not the call

The sharpest lesson in this project's history: **assert on what happened,
not on what was invoked.**

Reaching `/admin/login/` proves a form renders. It says nothing about
whether anyone can sign in — for a long time nobody could, and the check
was green. Now it signs in:

```python
signed_in = await client.post("/admin/login/", data={"email": ..., "password": ...})
check("POST /admin/login/", signed_in.status_code, 302)
dashboard = await client.get("/admin/", cookies=signed_in.cookies)
check("GET /admin/ signed in", dashboard.status_code, 200)
```

Likewise a dispatched job. That a job was queued is not that it ran:

```python
check("welcome email job ran", await _job_ran(jobs_log), True)
```

###  Verify your assertion can fail

An assertion that cannot fail is worth nothing, and you cannot tell by
reading it. Break the thing on purpose and watch it go red:

```console
$ # comment out the dispatch
$ uv run python scripts/smoke.py
  FAIL  welcome email job ran              False
```

```console
$ # comment out user_model=User
$ uv run python scripts/smoke.py
  FAIL  POST /admin/login/                 500
```

Both of those confirmed a real check. It takes thirty seconds and it is
the only way to know.

##  What CI runs

```yaml
- name: Lint
  run: |
    uv run ruff check .
    uv run ruff format --check .

- name: Apply migrations
  run: |
    cp .env.example .env
    make migrate

- name: Test
  run: uv run pytest -q

- name: Create an administrator
  env:
    ADMIN_PASSWORD: Ci-password1!
  run: uv run sillo user:admin ci@example.com ci

- name: Boot the application
  run: uv run python scripts/smoke.py
```

On Python 3.11, 3.12 and 3.13, on every push, and once a week on a
schedule.

<aside>

**The weekly run is not busywork.** The failure it catches is a new sillo
release breaking the project — which happens on the framework's calendar,
not on yours. A scheduled run turns "someone discovers this in three
months" into "we knew on Monday".

</aside>

`make migrate` in CI is also a real check: it runs the committed migration
against an empty database, which is exactly what a new contributor does.

##  Local equivalents

```bash
make check      # lint + test + smoke, the same three
make lint       # ruff check and format --check
make format     # apply both
```

Run `make check` before pushing and CI holds no surprises.

##  Testing background jobs

Call `handle()` directly — it is an ordinary coroutine, and this needs no
worker:

```python
async def test_welcome_email_skips_a_deleted_user(caplog):
    job = SendWelcomeEmail(user_id=999)

    await job.handle()

    assert "no longer exists" in caplog.text
```

For the queue itself, `perform_now` runs the job inline and gives you the
return value and any exception, which is usually what a test wants:

```python
result = await Resize.perform_now("avatar.png", width=256)
```

Reserve full worker round-trips for testing the queue wiring, not your
job's logic. They need a running worker and a real wait, and an idle
worker sleeps between polls — a test that waits 100ms will flake.

##  Things that will bite you

1. **Use `TestClient` as a context manager.** Without the `with`, the
   lifespan never runs and the ORM is uninitialised.

2. **Set `DATABASE_URL` before importing `app.config`**, or you are
   testing against your development database.

3. **A row created outside the app needs its own connection.**
   Connections are task-scoped; a plain `await User.create(...)` from a
   test raises `No TortoiseContext is currently active`.

4. **Do not assert on log lines you have not configured.** `caplog` needs
   the logger at the right level; the starter's job logger is `app.jobs`.

5. **`make smoke` writes to your development database** unless you point
   `DATABASE_URL` elsewhere. It creates a user each run.

##  Related

- [Creating a Project](/guides/start/) — what CI does on the starter itself
- [The Console](/guides/start/console/) — the commands CI drives
- [Background Work](/guides/start/background-work/) — testing jobs
- [Deployment](/guides/start/deployment/) — what to check before shipping
