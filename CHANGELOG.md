# Changelog

All notable changes to Sillo are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

Five findings, reported privately on 2026-08-12 and fixed here. The first two
chain into unauthenticated account takeover for any application using the file
session backend; that backend is not the default, so an application on the
signed-cookie default was never exposed to them.

- **A session cookie could read and write any file on the machine.**
  `FileSessionManager` joined the cookie's value straight into a path, so
  `session_id=../../../../etc/cron.d/x` addressed a file outside the session
  directory — arbitrary read through the load path, arbitrary write through the
  save path, from one request, with no authentication. `os.path.join` made it
  worse than traversal: an absolute value discarded the configured directory
  altogether, so `/root/.ssh/authorized_keys` needed no `../` at all.

  A key must now match `[A-Za-z0-9_-]{1,128}`, which is wider than the 64 hex
  characters `generate_session_key` produces so a project that overrides the
  generator keeps working, and excludes every character that can address
  another directory. A cookie that fails is treated as though none was sent —
  the visitor gets a new session rather than an error, so the response cannot
  be used to probe the filesystem. `_get_file_path` additionally resolves the
  result and refuses anything that leaves the store, which covers what the
  pattern did not anticipate, a symlinked storage directory among them.

- **Logging in did not change the session identifier.** `login()` wrote the
  user into the session and nothing else, so an identifier known before
  authentication was still valid after it: an attacker who fixed a session key
  in a victim's browser held an authenticated session the moment the victim
  signed in, without stealing a cookie. `Session.cycle_key()` is new and
  `login()` calls it. The new record is written before the old one is purged,
  so a failure part-way through leaves a session that still works rather than
  one dropped from under a signed-in user.

- **`allow_origins=["*"]` returned `Access-Control-Allow-Credentials: true` to
  every caller.** `allow_credentials` defaulted to `True`, and a wildcard was
  answered by reflecting the caller's own `Origin` rather than sending `*`.
  Browsers reject a literal `*` on a credentialed request, and reflecting is
  precisely what evades that check — so any site could read responses
  authenticated as your users. This was the configuration our own docstrings
  showed.

  `allow_credentials` now defaults to `False`, and combining it with a wildcard
  raises at construction rather than being quietly downgraded: both readings of
  that configuration are plausible, and guessing would leave whoever wrote it
  believing the other. A wildcard now answers with the literal `*`, so the
  response no longer varies by caller and a shared cache cannot serve one
  origin's headers to another.

- **`update_from_dict()` wrote any field named to it.** Handed a request body
  it would set any column, including the ones deciding what a user may do. The
  documentation already warned against passing an unvalidated body, which is
  weaker than not doing it: models may now declare `fillable` or `guarded`, and
  a single call may pass `only=`. A model that states none of them behaves
  exactly as before, since plenty of callers pass a dict they built.

- **A server-side session was never deleted.** `Session.save()` cleared
  `deleted` *before* handing the session to the backend, so `if session.deleted`
  was unreachable in both shipped stores and logging out overwrote the file with
  `{}` instead of removing it. No data survived, so this was not exploitable —
  but the delete path could not be tested, and session files accumulated
  forever. The flags are now cleared after the backend runs.

  Fixing that exposed the reason it had gone unnoticed: `deleted` meant two
  things. `__delitem__` and `delete()` set it for removing *one key*, while the
  backends read it as "purge this session". It now means only the second, which
  is what `clear()` sets.

### Changed

- **`logout()` empties the whole session** rather than removing the one entry
  `session_key` names. A server-side store purges its record and the browser is
  sent an expired cookie, so the identifier logged out of stops being usable by
  anyone still holding it. Anything else the session carried goes with it. The
  `session_key` argument is still accepted and now selects nothing, because
  everything is removed. This is what `Session.clear()` already documented
  itself as being for.

- **`CorsConfig(allow_credentials=...)` defaults to `False`.** An application
  relying on the old default must now say so, and cannot pair it with `"*"`.

## [0.0.2a3] - 2026-08-10

### Fixed

- **A 405 response no longer permanently breaks a route.** `Route.handle`
  assigned a fresh `JSONResponse` to `self.app` the first time a disallowed
  method hit the route, silently replacing the real handler and its
  middleware chain: every later request — even with an allowed method —
  received 405 forever. The 405 is now built per request and returned
  directly, with a proper `{"detail": "Method Not Allowed"}` body and a
  sorted `Allow` header.

  Also fixed in the same pass: the dispatch loop leaking the last
  iteration's `matched_params` onto the first partial match, a dead
  `prefix.rstrip("/")` no-op, and per-request rebuilding of a lowercased
  method generator (methods are now compared in a single `set` check).
  OpenAPI generation iterates sorted methods so the generated docs are
  deterministic.

## [0.0.2a2] - 2026-08-09

### Removed

- **`silloApp` is gone.** 0.0.2a1, released hours earlier, kept it resolvable
  behind a `DeprecationWarning`. That bridge is removed: `from sillo import
  silloApp` now raises `ImportError`, and `sillo.silloApp` raises
  `AttributeError`.

  ```python
  from sillo import SilloApp

  app = SilloApp(title="Projects API")
  ```

  The reasoning against a deprecation period is that an alias which still
  works is an alias people keep writing, and every copy of it that reaches a
  tutorial or a StackOverflow answer outlives the release that removed it.
  The framework is early enough that a clean break costs less than a name
  nobody can trust.

  The failure is deliberately immediate and loud. Nothing resolves to a shim,
  a subclass or `None` — an old call site fails at import, before any of your
  code runs, rather than somewhere further in.

  If you are coming from 0.0.2a1, run your suite with
  `-W error::DeprecationWarning` first; it will point at every remaining use.

## [0.0.2a1] - 2026-08-09

### Changed

- **The application class is now `SilloApp`.** It was `silloApp`, which is a
  spelling no Python convention endorses — classes are `CapWords`, and a
  lowercase-initial name reads as a function at every call site, which is
  exactly how `app = silloApp()` looked.

  The old name still resolves, from both `sillo` and `sillo.application`, and
  emits a `DeprecationWarning` naming its removal in **0.1.0**. (Superseded:
  0.0.2a2 removed it instead. This entry describes 0.0.2a1 as released.)
  Nothing breaks on upgrade; the migration is one find-and-replace:

  ```python
  from sillo import SilloApp

  app = SilloApp(title="Projects API")
  ```

  `silloApp` is deliberately *not* in `__all__`, so a star-import and any
  editor completion offer only the new name.

  `str(app)` now reads `<SilloApp: title>`, which matters to anyone matching
  on dev-server output.

### Fixed

- **A release could ship with `sillo.__version__` reporting the wrong
  version.** The release workflow compared the tag against `pyproject.toml`
  only, so 0.0.1a15 published with the module still saying `0.0.1a14` and the
  job reported success. The check now covers `sillo/__init__.py` as well, and
  fails the release when the three disagree.

## [0.0.1a15] - 2026-08-08

### Fixed

Everything under this heading was found by giving CI a Redis server. The Redis
tests had always skipped themselves — no workflow ran a Redis container — so
the cache backend, the queue backend and the pub/sub transport shipped with
tests that had never executed anywhere.

- **`RedisBackend.dequeue()` raised on every call.** `BZPOPMIN` replies with
  `(key, member, score)` and the result was unpacked into two names, so every
  dequeue ended in `ValueError: too many values to unpack`. The Redis queue
  backend could not deliver a single task.

- **Redis queue priority was inverted.** Tasks are scored
  `-priority * 1e12 + created_at`, so a higher priority is a *lower* score —
  which is what lets the memory backend pop from a min-heap. The Redis backend
  popped with `BZPOPMAX`, serving the lowest-priority task first.

- **`RedisBackend.is_duplicate()` never deduplicated.** It checked whether the
  key existed but never claimed it, so it returned `False` forever. It is now
  a `SET NX` check-and-set, matching `MemoryBackend` and safe against two
  workers racing on the same key.

- **`RedisTransport.subscribe()` deadlocked after `start()`.** The listener
  loop held the pubsub connection open inside `listen()`, and redis-py's
  `PubSub` is a single connection that cannot be used from two places at once,
  so a subscribe waited on a connection the loop would never release. It
  blocked the event loop itself — even `asyncio.wait_for` around the call
  could not fire. Subscribing after `start()` is the normal path, so this hung
  for anyone using the transport as documented. The loop now polls with
  `get_message` under a lock.

- **Registering an event listener never subscribed to anything.**
  `EventEmitter._subscribe` called the coroutine function `subscribe()` and
  discarded the coroutine — "coroutine was never awaited" — and the deferral
  its docstring described did not exist either, because nothing recorded the
  name and `start()` never looked. Channels registered before the loop exists
  are now subscribed by `start()`.

- **Reading a cache key extended its life.** `RedisCache.get()` refreshed the
  TTL on every read, and a `None` TTL resolves to `default_ttl` — so an entry
  written with `ttl=1` had its expiry pushed out to the backend default the
  moment anything read it. Only entries written with `sliding=True` are
  refreshed now.

- **A `sliding=True` value read back as its internal wrapper**, i.e.
  `{"_value": ..., "_sliding": True, ...}` instead of the value stored.

And, separately:

- **Session settings were accepted and silently ignored.** `SessionConfig` took
  `**kwargs` and merged them unchecked, and `SessionMiddleware` forwarded its
  keyword arguments to `BaseMiddleware`, which accepts anything and reads none
  of it. Passing `cookie_secure=False` — the name the documentation used — left
  the real `session_cookie_secure` at `True`, so the cookie went out marked
  `Secure` and browsers stopped returning it over plain HTTP. Sessions did
  nothing at all in local development, with no error to point at.

  Unknown settings now raise a `TypeError` naming the closest real setting, and
  settings passed to `SessionMiddleware` reach the configuration. Reading an
  attribute that is not a setting raises `AttributeError` rather than returning
  `None`.

- **`SessionConfig(manager=...)` was a documented setting that nothing read.**
  Only `SessionMiddleware(manager=...)` had any effect. The config's value is
  now used when the middleware is not given one, and passing a class where an
  instance is required raises with the correct form.

- **`import sillo` depended on import order.** `sillo/middleware/__init__.py`
  imported `sillo.security`, which imported `BaseMiddleware` back from the
  partially-initialised package. It worked only because the local import
  happened to come first; sorting those two lines raised `ImportError`.
  Security modules now import from `sillo.middleware.base` directly.

### Changed

- **CI runs Redis.** `run-tests.yaml` gets a Redis service container and fails
  if the Redis tests report themselves as skipped, since a skip is exactly the
  failure the job exists to prevent.

- **CI runs `ruff check`.** It never had; only `ruff format` ran, so 2991
  findings had accumulated. 2693 were mechanical and are fixed. The remainder
  are listed in `[tool.ruff.lint] ignore` in `pyproject.toml` as a named
  backlog rather than a blanket exemption.

- **`target-version` is `py310`, matching `requires-python`.** It said `py38`,
  four releases below anything this package installs on, which alone produced
  442 findings demanding `from __future__ import annotations` for syntax every
  supported version understands.

- `ruff` and `ty` are upper-bounded. Both are pre-1.0 and gate CI, so on a
  floor constraint an upstream release turned the build red with no change
  here.

- `actions/setup-python` is v5 across all workflows.

## Released

Releases up to `0.0.1a14` predate this file; see the git history.

Note that `0.0.1a7` and earlier fail on `import sillo` unless the `record`
extra is installed, because the import chain reached `tortoise` at module
scope. `0.0.1a6` is yanked; the others are not.
