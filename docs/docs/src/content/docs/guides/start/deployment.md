---
title: Deployment
description: "Taking a Sillo project to production: settings, migrations, workers, static files, a reverse proxy, and the checks worth running before you ship."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Deploying a Sillo Project
  - tag: meta
    attrs:
      property: og:description
      content: Settings, migrations, workers, static files and a reverse proxy for a Sillo project.
---

#  Deployment

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Under a process manager, behind a reverse proxy. Everything else on this page
is what to change before that is a good idea.

:::caution[Not `sillo serve`]
`sillo serve` is the **development** server. It is a single process by default,
its `--reload` restarts on any file change, and its access log is formatted for
a person watching a terminal rather than for a log collector. It also supervises
nothing: a worker that dies stays dead.

Run `uvicorn` directly, as above, with systemd or your orchestrator restarting
it. That is the same server `sillo serve` uses underneath — what changes is the
configuration and who is watching it.
:::

##  Settings

```bash
APP_ENV=production
DEBUG=false
SECRET_KEY=<a real secret>
DATABASE_URL=postgres://user:password@host:5432/myapp
CORS_ALLOW_ORIGINS=https://myapp.example.com
LOG_LEVEL=info
```

**`DEBUG=false`** matters. With it on, error responses carry tracebacks (your
file paths, your local variables) to whoever provoked them.

**`SECRET_KEY` signs sessions.** A shared or published one lets anyone
forge a session cookie. Generate one per environment:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`sillo-start` does this when it creates the project. It does **not** happen when you
copy `.env` between machines, which is the moment to check.

**`CORS_ALLOW_ORIGINS` should name your front end**, not `*`. The default
is a local Vite server, which is wrong everywhere else.

:::note
**Nothing is read from a file at runtime.** `app/config.py` declares the
settings and their types; `.env` is loaded at import for convenience in
development. In production, set real environment variables. A container image
should not contain a `.env`.
:::

##  Migrations

Run them as a **separate step before the new version starts**, never from
application startup code:

```bash
uv run sillo db:migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Three replicas that each migrate on boot produce three concurrent schema
changes and, on a good day, two failures.

For rolling deployments, make it a job that runs once and gates the
rollout, and keep each migration compatible with **both** the old and the
new application version:

- add a column before the code that writes to it
- drop a column a release after the code that read it is gone
- add an index concurrently, in its own migration

```bash
uv run sillo db:plan     # what would run, before it runs
```

is worth putting in front of a production migration.

##  Workers

If you use the queue, run it properly:

```bash
QUEUE_URL=redis://redis:6379 uv run sillo queue:work --concurrency 8
```

The in-memory queue does not survive a restart and is not shared between
processes, so with more than one application replica it is not a queue. It is
four separate queues that each lose their contents on deploy.

```python
# app/bootstrap.py — drop in_process for a real deployment
_register_work(application)
```

`run_worker` installs a SIGTERM handler, so a container stop finishes the
job in flight rather than killing it halfway.

:::caution
**Run one scheduler, not one per replica.** Each application process
running `_register_work` gets its own scheduler, so a nightly task fires
once per replica. Run `sillo schedule:run` as a single process, or guard
the task with a lock.
:::

##  Static files

Serve them with a web server, not with Python:

```nginx
location /static/ {
    alias /srv/myapp/static/;
    expires 30d;
}

location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The `/static` mount in `bootstrap.py` is for development and small
deployments. With a proxy in front it never sees traffic.

The forwarded headers matter: without `X-Forwarded-Proto`, the application
believes it is on HTTP and will mark secure cookies wrongly.

##  Workers and SQLite do not mix

```bash
uvicorn app.main:app --workers 4      # with SQLite: contention and locking
```

Several processes writing one SQLite file contend for locks and will
produce `database is locked` under any real load.

Use PostgreSQL or MySQL in production, or stay on a single worker. SQLite
is an excellent default for development and a poor one for concurrency.

##  A container

```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /srv/myapp
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV APP_ENV=production DEBUG=false
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`--frozen` installs exactly what `uv.lock` records, so the image matches
what you tested. `--no-dev` leaves pytest and ruff out.

Migrations belong in the **deployment**, not in `CMD`, otherwise every replica
migrates:

```yaml
# one job, before the rollout
command: ["uv", "run", "sillo", "db:migrate"]
```

##  A systemd unit

```ini
[Unit]
Description=Myapp
After=network.target

[Service]
Type=exec
User=myapp
WorkingDirectory=/srv/myapp
EnvironmentFile=/etc/myapp.env
ExecStart=/usr/local/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

And the worker, if you have one:

```ini
[Service]
ExecStart=/usr/local/bin/uv run sillo queue:work --concurrency 8
Restart=always
KillSignal=SIGTERM
TimeoutStopSec=60
```

`TimeoutStopSec` should exceed your longest job, so a restart lets the job
in flight finish rather than killing it.

##  The admin in production

It is on by default at `/admin/`. Decide deliberately:

```bash
ADMIN_ENABLED=false        # not in this deployment
ADMIN_PREFIX=/staff-only   # or somewhere less obvious
```

Access is `is_staff`, checked on **every request**, so revoking it takes effect
immediately rather than at that person's next sign-in.

The query console at `/admin/query/` grants read and write on every table
and is superuser-only. If that is more power than you want to exist in
production, disable the admin there and use it against a replica.

##  Before you ship

A checklist that is short because each item has cost someone a bad
afternoon:

- [ ] `DEBUG=false`
- [ ] `SECRET_KEY` unique to this environment, not copied from `.env.example`
- [ ] `DATABASE_URL` pointing at PostgreSQL or MySQL, not SQLite, if you run more than one worker
- [ ] `CORS_ALLOW_ORIGINS` naming real origins, not `*`
- [ ] Migrations run as a separate step, gating the rollout
- [ ] `sillo db:plan` reviewed for anything destructive
- [ ] Static files served by the proxy
- [ ] `X-Forwarded-Proto` set by the proxy
- [ ] Worker running with `QUEUE_URL`, if you dispatch jobs
- [ ] Exactly one scheduler, if you have scheduled tasks
- [ ] An administrator account created
- [ ] Lint, tests and the smoke check green on the commit being deployed

##  Health checks

`/api/health` is provided and cheap:

```yaml
livenessProbe:
  httpGet: { path: /api/health, port: 8000 }
  initialDelaySeconds: 10
  periodSeconds: 30
```

For a readiness probe that means "can serve traffic", add one that touches the
database. The manager exposes `health()`:

```python
@router.get("/ready")
async def ready(request, response):
    manager = request.app.state["record"]
    return response.json({"ready": await manager.health()}, status_code=200)
```

A liveness probe that queries the database will restart your application
whenever the database hiccups, which is rarely what you want. Keep them
distinct.

##  Logging

```bash
LOG_LEVEL=info
```

`DB_ECHO=true` logs every query. Useful locally; in production it is a
performance problem and a way to write credentials into logs.

The application logs its own lifecycle at startup: "Database connected", and
the reverse at shutdown. The console quiets those, because they are noise
around a one-shot command and signal in a long-running process.

##  Upgrading sillo

The starter pins a floor:

```toml
"sillo-framework[cache,hashing-bcrypt,jwt,record,templating]>=0.0.1a8",
```

To move:

```bash
uv lock --upgrade-package sillo-framework
ruff check . && pytest && python scripts/smoke.py
```

That last line is the point of the sequence. It lints, tests, and boots the
application against the new version, which is what catches a release that
changes something your project depends on.

The starter's own CI runs weekly for the same reason.

##  Things that will bite you

1. **`--workers 4` with SQLite** produces lock contention under load.

2. **Migrating from application startup** races across replicas.

3. **Copying `.env` between environments** copies the signing key with
   it.

4. **Forgetting `X-Forwarded-Proto`** makes the application think it is
   on HTTP.

5. **`sillo serve --reload` is not a production server.** It is one process with
   reload watching your files.

6. **One scheduler per replica** means your nightly job runs four times.

##  Related

- [Creating a Project](/guides/start/): what you are deploying
- [Database & Migrations](/guides/start/database/): migrating safely
- [Background Work](/guides/start/background-work/): workers in production
- [Testing](/guides/start/testing/): the suite and the smoke check
- [The Console](/guides/start/console/): the commands a deployment runs
