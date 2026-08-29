---
title: Model Events
description: "Lifecycle hooks on a model: the eight events, registering callbacks with @Model.on, grouping them into an observer, and where events are the wrong tool."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Model Events
  - tag: meta
    attrs:
      property: og:description
      content: before/after create, save, update and delete, callbacks and observers.
---

```python
from sillo.record import Model
from sillo.record.events import HasEvents


class Post(Model, HasEvents):
    title = fields.CharField(max_length=200)
    slug = fields.CharField(max_length=200)


@Post.on("before_create")
async def fill_slug(post):
    if not post.slug:
        post.slug = slugify(post.title)
```

## The eight events

| Event | When |
| --- | --- |
| `before_create` | Before a new row is inserted |
| `after_create` | After it is inserted |
| `before_save` | Before any save, insert or update |
| `after_save` | After any save |
| `before_update` | Before an existing row is updated |
| `after_update` | After it is updated |
| `before_delete` | Before a delete |
| `after_delete` | After it |

Every callback is `async` and receives the instance.

A `before_*` callback can mutate the instance, and the change is part of the
write, which is what makes `before_create` the right place to fill in a derived
field.

## Registering

The decorator, for one callback:

```python
@Post.on("after_create")
async def notify(post):
    await queue.dispatch(NotifySubscribers(post_id=post.id))
```

Several callbacks on the same event all run, in registration order.

## Observers

When a set of hooks belongs together, group them:

```python
from sillo.record.events import ModelObserver


class PostObserver(ModelObserver):
    async def before_create(self, post):
        post.slug = post.slug or slugify(post.title)

    async def after_create(self, post):
        await search_index.add(post)

    async def after_update(self, post):
        await search_index.update(post)

    async def after_delete(self, post):
        await search_index.remove(post.id)


Post.observe(PostObserver())
```

`ModelObserver` defines all eight as no-ops, so you override only what you
need.

An observer is the better shape once you have more than two hooks: the
lifecycle reads top to bottom in one class, and a change to the search index
integration is one file rather than four decorators scattered around.

Register observers where the models are imported
(`database/models/__init__.py`) so importing a model is enough to have its
behaviour.

## Firing manually

```python
await Post.fire_event("after_create", post)
```

Rarely needed. Useful when a bulk path has done work the events should still
know about. See [what does not fire events](#what-does-not-fire-events).

## What does not fire events

Events are dispatched from the instance methods. These paths do not go through
them:

- `QuerySet.update()` and `QuerySet.delete()`: set-based SQL, no instances;
- `bulk_create`, `bulk_upsert` and `upsert`;
- raw SQL;
- anything another process does.

That is not an oversight (loading a million rows to fire a callback would
defeat the point of a bulk statement) but it is the reason model events cannot
be an audit log or a security control. Both need to be true for *every* writer.

Put those in the database (a trigger, a constraint) or in the layer above (a
service function every caller goes through).

## Failure semantics

An exception in a callback propagates. A `before_*` failure prevents the write;
an `after_*` failure happens once the write has already occurred.

That asymmetry matters for anything in an `after_*` hook. If the search index
is down, this raises:

```python
@Post.on("after_create")
async def index(post):
    await search_index.add(post)      # the post exists; this fails
```

Wrap the write in a [transaction](/v1.0/orm/transactions/) if the two must be
atomic, or (usually better) dispatch a [queued job](/v1.0/guides/work/queue/) so a
flaky third party cannot fail a request:

```python
@Post.on("after_create")
async def index(post):
    await queue.dispatch(IndexPost(post_id=post.id))
```

## Events versus the alternatives

| Instead of | Use |
| --- | --- |
| Validating in `before_save` | [`ValidatesBeforeSaveMixin`](/v1.0/orm/mixins/#validatesbeforesavemixin): same timing, clearer name |
| Cascading deletes in `before_delete` | A database `on_delete=CASCADE` |
| Cross-aggregate work in `after_save` | An [application event](/v1.0/guides/events/) or a [job](/v1.0/guides/work/jobs/) |

Model events are for things intrinsic to the row: deriving a field, keeping a
denormalised counter, stamping a value. Once a hook starts reaching into other
parts of the system, it belongs at the application layer where it can be seen.
