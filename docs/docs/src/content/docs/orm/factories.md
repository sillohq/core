---
title: Factories
description: "Building model instances for tests: the Factory class, make and create, states, relationships, and the FactoryBuilder registry."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Factories
  - tag: meta
    attrs:
      property: og:description
      content: Factory, make, create, create_many, states and FactoryBuilder.
---

A factory knows how to build a valid instance of a model, so a test can ask for
one without restating every required field.

```python
from uuid import uuid4
from sillo.record.factories import Factory
from database.models import User


class UserFactory(Factory):
    model = User
    definition = staticmethod(lambda: {
        "email": f"user{uuid4().hex[:8]}@example.test",
        "username": f"user{uuid4().hex[:8]}",
        "is_active": True,
    })
```

```python
user = await UserFactory.create()
users = await UserFactory.create_many(5)
draft = UserFactory.make()                       # unsaved
admin = await UserFactory.create({"is_staff": True})
```

## Why this instead of literals

A test that writes the model out by hand:

```python
user = await User.create(
    email="a@b.com", username="a", is_active=True, is_staff=False,
)
```

…says four things, three of which the test does not care about. When the model
gains a required field, every such test breaks at once, and each has to be
edited to add a value nobody is asserting on.

A factory says the required fields once. A test then names only what it is
actually about:

```python
staff = await UserFactory.create({"is_staff": True})
```

Which reads as "a user who is staff", because that is the only thing stated.

## `definition`

A callable returning a dict of defaults. It is called **per instance**, which
is what lets it generate unique values:

```python
definition = staticmethod(lambda: {"email": f"user{uuid4().hex[:8]}@example.test"})
```

:::caution[Wrap it in `staticmethod`]
`definition` is a class attribute holding a function. Assigned bare, Python
binds it as a method and passes `cls`, and the lambda above raises
`TypeError`.

`staticmethod(...)` (or a plain `def` decorated with `@staticmethod`) keeps it
a function.
:::

Use a real generator for unique fields. A hardcoded email means the second
`create()` in a test violates a unique constraint, and the failure looks like a
bug in the code under test rather than in the factory.

## `make` and `create`

```python
UserFactory.make()                    # instance, not saved
UserFactory.make({"username": "ada"})

await UserFactory.create()            # saved
await UserFactory.create({"username": "ada"})
await UserFactory.create_many(5)
await UserFactory.create_many(5, {"is_active": False})
```

`make` is for testing something that operates on an unsaved instance: a
serialiser, a validator, a form. It touches no database, so it is fast enough
to use freely.

`create_many` saves one at a time, so [model events](/orm/events/) and
[validation](/orm/mixins/#validatesbeforesavemixin) all run. For hundreds of
rows where you do not need either, [`bulk_create`](/orm/bulk/) is much faster.

The `overrides` in `create_many` apply to **every** instance. For rows that
should differ, loop.

## States

A named variation:

```python
class UserFactory(Factory):
    model = User
    definition = staticmethod(lambda: {...})


class AdminFactory(UserFactory):
    definition = UserFactory.state(is_staff=True, is_superuser=True)
```

```python
admin = await AdminFactory.create()
```

`state()` returns a new definition callable. The parent's, with those keys
overridden. Subclassing is what gives it a name.

For a one-off, an override at the call site is simpler. Reach for a state when
the same variation appears in several tests, so the meaning of "an admin" lives
in one place.

## Relationships

Factories do not resolve relations for you. Create the parent, pass its id:

```python
class PostFactory(Factory):
    model = Post
    definition = staticmethod(lambda: {"title": "A post", "body": "…"})


author = await UserFactory.create()
post = await PostFactory.create({"author_id": author.id})
```

To make the parent implicit, override `create`:

```python
class PostFactory(Factory):
    model = Post
    definition = staticmethod(lambda: {"title": "A post", "body": "…"})

    @classmethod
    async def create(cls, overrides=None):
        overrides = dict(overrides or {})
        if "author_id" not in overrides:
            overrides["author_id"] = (await UserFactory.create()).id
        return await super().create(overrides)
```

Only when the parent is genuinely incidental. A test that creates a user it
never mentions is harder to read, not easier, and it hides how many rows the
test is writing.

## `FactoryBuilder`

A registry, for looking factories up by name:

```python
from sillo.record.factories import FactoryBuilder

factories = FactoryBuilder()
factories.register("user", UserFactory)
factories.register("post", PostFactory)

user = await factories.get("user").create()
```

An unregistered name raises `KeyError` naming it.

This is for the case where the factory is chosen at runtime, a seeding command
driven by configuration, or a fixture format that names models as strings.
Importing the class directly is clearer everywhere else.

## In tests

An in-memory SQLite database per test gives you isolation with no teardown:

```python
import pytest
from sillo.record import DatabaseConfig, DatabaseManager


@pytest.fixture
async def database():
    manager = DatabaseManager(DatabaseConfig.sqlite(":memory:"))
    manager.register_models("database.models")
    await manager.init()
    yield manager
    await manager.shutdown()


async def test_admin_can_sign_in(database):
    admin = await UserFactory.create({"is_staff": True})
    ...
```

`:memory:` is per connection, so each test's database starts empty and
vanishes, no truncation, no ordering dependencies between tests.

## See also

- [Seeding and fixtures](/orm/seeding/): for populating a real database.
- [Test client](/guides/start/testing/): the HTTP side of a test.
