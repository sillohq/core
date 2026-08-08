# Changelog

All notable changes to Sillo are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
