---
title: Relationships
description: "Foreign keys, one-to-one and many-to-many on a Sillo model: declaring them, related names, delete behaviour, through tables, and how to traverse them without an N+1."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Relationships
  - tag: meta
    attrs:
      property: og:description
      content: ForeignKeyField, OneToOneField, ManyToManyField, related names and delete behaviour.
---

```python
from tortoise import fields
from sillo.record import Model


class Author(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100)


class Post(Model):
    id = fields.IntField(primary_key=True)
    title = fields.CharField(max_length=200)
    author = fields.ForeignKeyField("models.Author", related_name="posts")
    tags = fields.ManyToManyField("models.Tag", related_name="posts")
```

The target is `"<app>.<Model>"`. `models` is the default app label, the same
one [migrations](/orm/migrations/#the-app-label) use. A string rather than the
class lets two models reference each other without an import cycle.

## Foreign keys

```python
author = fields.ForeignKeyField(
    "models.Author",
    related_name="posts",
    on_delete=fields.CASCADE,
    null=False,
    db_constraint=True,
)
```

Declaring `author` gives you **two** attributes:

```python
post.author        # the related object — must be fetched first
post.author_id     # the raw column, always present
```

`author_id` is the one to use when you only need the id. It is already loaded,
so it costs nothing:

```python
if post.author_id == request.user.id:      # no query
    ...

if (await post.author).id == request.user.id:   # a query, for the same answer
    ...
```

### Fetching

```python
post = await Post.get(id=1)
await post.fetch_related("author")
print(post.author.name)
```

Or ask for it in the query, which is almost always what you want:

```python
post = await Post.get(id=1).prefetch_related("author")
posts = await Post.all().select_related("author")
```

Touching an unfetched relation raises rather than silently querying. That is
deliberate, an implicit query inside a loop is how an N+1 hides. See [Eager
loading](/orm/eager-loading/).

### The reverse side

`related_name="posts"` creates `author.posts`:

```python
author = await Author.get(id=1)
await author.fetch_related("posts")
for post in author.posts:
    ...
```

It is also a queryset, so you can filter it:

```python
recent = await author.posts.filter(status="published").order_by("-created_at").limit(5)
```

Omit `related_name` and it defaults to `<model>s` lowercased. Pass
`related_name=False` to create no reverse accessor at all, useful when a model
is referenced from many places and none of the reverse sides are meaningful.

Two foreign keys to the same model **need** distinct related names, or the
second collides with the first:

```python
class Message(Model):
    sender = fields.ForeignKeyField("models.User", related_name="sent_messages")
    recipient = fields.ForeignKeyField("models.User", related_name="received_messages")
```

### `on_delete`

What happens to this row when the referenced row is deleted:

| Value | Behaviour |
| --- | --- |
| `CASCADE` | Delete this row too. **The default.** |
| `RESTRICT` | Refuse the delete while this row exists |
| `SET_NULL` | Set the column to `NULL`. Requires `null=True`. |
| `SET_DEFAULT` | Set it to the field's default |
| `NO_ACTION` | Leave it to the database |

```python
from tortoise import fields

author = fields.ForeignKeyField("models.Author", on_delete=fields.RESTRICT)
```

:::caution[The default is CASCADE]
Deleting an author deletes their posts, and the posts' comments, and so on
through the graph, in one statement, with no confirmation and no way back.

That is right for genuinely owned data (an order's line items) and wrong for
anything with independent value. Pick deliberately: `RESTRICT` makes the
deletion fail loudly, which is usually what you want for a record someone might
delete by accident.

Better still, do not delete, [soft delete](/orm/mixins/#softdeletesmixin), and
the question does not arise.
:::

This is enforced by the **database**, so it applies to every writer, including
migrations and other services. That is why it is preferable to
[`CascadesDeletesMixin`](/orm/mixins/#cascadesdeletesmixin), which only applies
to deletes going through the model.

### `db_constraint=False`

Declares the relationship to the ORM without creating a foreign key constraint
in the schema. For a legacy database, a cross-database reference, or a
partitioned table where the constraint is not supportable.

You lose referential integrity. Nothing stops a row pointing at an id that does
not exist. Only reach for it when the constraint genuinely cannot exist.

### Nullable foreign keys

```python
author = fields.ForeignKeyField("models.Author", null=True, on_delete=fields.SET_NULL)
```

Then `post.author_id` may be `None`, and every consumer has to handle it. Worth
it when the relationship is genuinely optional; not worth it as a way to avoid
deciding.

## One-to-one

```python
class Profile(Model):
    user = fields.OneToOneField("models.User", related_name="profile")
    bio = fields.TextField()
```

A foreign key with a unique constraint. The reverse side is a single object
rather than a collection:

```python
await user.fetch_related("profile")
user.profile.bio
```

Use it to split a table that has two distinct lifetimes (a rarely-read profile
beside a hot user row) or to attach optional data without widening the main
table. If every user always has one and you always load both, they are one
table.

## Many-to-many

```python
class Post(Model):
    tags = fields.ManyToManyField("models.Tag", related_name="posts")
```

Tortoise creates the join table for you.

```python
tag = await Tag.get(name="python")

await post.tags.add(tag)
await post.tags.remove(tag)
await post.tags.clear()

await post.fetch_related("tags")
for tag in post.tags:
    ...
```

`add` and `remove` take several at once:

```python
await post.tags.add(python, async_tag, tutorial)
```

Both sides work the same way. `tag.posts.add(post)` is the same row.

### Filtering across it

```python
await Post.filter(tags__name="python")
await Tag.filter(posts__status="published").distinct()
```

A join across a many-to-many produces one row per match, so a tag on three
published posts appears three times. [`distinct()`](/orm/values/#distinct) is
what collapses them.

### A custom through table

The generated join table holds only the two keys. When the relationship itself
has attributes (when it was added, by whom, in what order) model it explicitly:

```python
class PostTag(Model):
    post = fields.ForeignKeyField("models.Post", related_name="post_tags")
    tag = fields.ForeignKeyField("models.Tag", related_name="post_tags")
    added_at = fields.DatetimeField(auto_now_add=True)
    added_by = fields.ForeignKeyField("models.User", null=True)

    class Meta:
        unique_together = (("post", "tag"),)
```

Now you create rows in `PostTag` directly rather than calling `.add()`. That is
the trade: you get the extra columns, and you lose the convenience methods.

`ManyToManyField(through="post_tag")` points the field at an existing table by
name, for adopting a schema you already have. For a *new* relationship with
attributes, two explicit foreign keys as above is clearer than a half-managed
one.

## Self-references

```python
class Category(Model):
    name = fields.CharField(max_length=100)
    parent = fields.ForeignKeyField(
        "models.Category", related_name="children", null=True,
    )
```

Traversing a tree is one query per level. For anything deeper than two or
three, a recursive CTE in [raw SQL](/orm/raw-sql/) is the right tool, or store
a materialised path (`"1/4/9/"`) and query it with a prefix match.

## Spanning relations in queries

`__` traverses, to any depth:

```python
await Post.filter(author__name="Ada")
await Post.filter(author__profile__country="GB")
await Comment.filter(post__author__is_staff=True)
```

Each level is a join. They are cheap on indexed foreign keys and not cheap
across a many-to-many. Check with [`explain()`](/orm/queries/#explain) when a
query gets deep.

## Ordering by a related field

```python
await Post.all().order_by("author__name")
```

## See also

- [Eager loading](/orm/eager-loading/): `select_related`, `prefetch_related`
  and the N+1
- [Lookups](/orm/lookups/): everything you can put after `__`
- [Field reference](/orm/field-reference/): the non-relational types
