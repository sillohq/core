---
title: Database Configuration
description: "DatabaseConfig in full — every field, the environment variables behind it, the URL builders for SQLite, PostgreSQL and MySQL, pooling and TLS."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Database Configuration
  - tag: meta
    attrs:
      property: og:description
      content: DatabaseConfig, its environment variables, and the per-backend URL builders.
---

`DatabaseConfig` is a dataclass. Every field has an environment default, so the
common case is one line:

```python
from sillo.record import DatabaseConfig

config = DatabaseConfig.from_env()
```

## Fields

| Field | Environment variable | Default |
| --- | --- | --- |
| `url` | `DATABASE_URL` | `sqlite://:memory:` |
| `backend` | *(derived from the URL)* | `sqlite` |
| `pool_size` | `DB_POOL_SIZE` | `5` |
| `max_overflow` | `DB_MAX_OVERFLOW` | `10` |
| `pool_recycle` | `DB_POOL_RECYCLE` | `3600` |
| `echo` | `DB_ECHO` | `false` |
| `ssl` | `DB_SSL` | `false` |
| `ssl_ca` | `DB_SSL_CA` | — |
| `ssl_cert` | `DB_SSL_CERT` | — |
| `ssl_key` | `DB_SSL_KEY` | — |
| `timezone` | `DB_TIMEZONE` | `UTC` |
| `charset` | — | `utf8mb4` |
| `generate_schemas` | `DB_GENERATE_SCHEMAS` | `true` |

```python
DatabaseConfig.from_env()                 # DATABASE_URL, DB_POOL_SIZE, …
DatabaseConfig.from_env(prefix="READ_")   # READ_DATABASE_URL, READ_DB_POOL_SIZE, …
```

The prefix is how you configure a second connection — a read replica, a
reporting database — from the same environment without the two colliding.

## URL forms

```
sqlite://storage/app.db
sqlite://:memory:
postgres://user:password@localhost:5432/dbname
mysql://user:password@localhost:3306/dbname
```

Two aliases are accepted and normalised: `postgresql://` becomes `postgres://`,
and `mariadb://` becomes `mysql://`. Both are what people actually type, and
both would otherwise be an unrecognised scheme.

## The builders

For when you have the parts rather than a URL:

```python
DatabaseConfig.sqlite("storage/app.db")
DatabaseConfig.sqlite()                     # ":memory:"

DatabaseConfig.postgres("myapp", "secret")
DatabaseConfig.postgres(
    "myapp", "secret",
    user="app", host="db.internal", port=5432,
)

DatabaseConfig.mysql("myapp", "secret", user="app", host="db.internal")
```

Each sets the backend as well as the URL, so nothing has to be inferred.

The builders escape what needs escaping. A password with an `@` or a `/` in it
breaks a hand-assembled URL in a way that produces a confusing connection error
rather than an obvious one — which is the main reason to prefer them.

## Backends

```python
from sillo.record import DatabaseBackend

DatabaseBackend.SQLITE
DatabaseBackend.POSTGRES
DatabaseBackend.MYSQL
DatabaseBackend.MARIADB
```

Each needs its driver installed — see [Setup](/orm/setup/#installing-the-driver).

### On SQLite

Right for tests, local development, and genuinely small single-process
deployments. It is a file with a single writer: concurrent writes serialise,
and a web application under load will meet `database is locked`.

`:memory:` is per connection, which makes it ideal for tests — each test gets a
clean database with no teardown — and useless for anything else, since a second
connection sees a different empty database.

## Pooling

`pool_size` and `max_overflow` apply to the server backends; SQLite ignores
them.

Size the pool against your database's connection limit, not your traffic. Every
application process holds up to `pool_size + max_overflow` connections, so four
processes at the defaults is up to 60 connections — comfortably past the
100-connection default of a small managed PostgreSQL once you add a worker and
a scheduler.

`pool_recycle` (seconds) closes and reopens connections older than that. It
exists because proxies and managed databases drop idle connections without
telling the client, and the failure surfaces as an occasional error on a
perfectly good query.

## `echo`

```bash
DB_ECHO=true
```

Logs every statement. Useful for finding an N+1; noisy enough that it should
never be on in production, where it puts query parameters into your logs.

Related: [`explain()`](/orm/queries/#explain) shows the plan for one query
instead.

## TLS

```bash
DB_SSL=true
DB_SSL_CA=/etc/ssl/certs/rds-ca.pem
DB_SSL_CERT=/etc/ssl/certs/client.pem
DB_SSL_KEY=/etc/ssl/private/client-key.pem
```

`DB_SSL=true` alone enables TLS with the system trust store, which is what a
managed database usually needs. The three paths are for mutual TLS, or a CA
that is not in the system store.

## Time zones

`DB_TIMEZONE` defaults to `UTC`, and should stay there.

Store UTC and convert at the edges. A database in local time is a database that
either loses an hour or repeats one every year, and the bug arrives at 2am on a
Sunday in October.

## Inspecting

```python
config.to_dict()
```

The configuration as a dict, for logging or a health endpoint.

:::caution[It contains the password]
`url` includes credentials. Do not log `to_dict()` as-is — mask it, or log only
the fields you need.
:::
