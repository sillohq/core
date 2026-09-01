---
title: Cost & Limits
description: Static analysis before execution — depth, aliases, breadth, document size, and a weighted cost that understands lists.
---

A GraphQL endpoint publishes a graph, and a graph with a cycle in it publishes
unbounded work behind a very small request:

```graphql
{ post { author { posts { author { posts { author { name } } } } } } }
```

A handful of bytes, and a table scan per level. Rate limiting by request count
does not help — the expensive request and the cheap one both count as one.

So the document is measured **before** execution and refused if it is too
large. Refusing afterwards would mean having already done the work.

```python
from sillo.graphql import Graph, Limits

Graph(schema, limits=Limits(depth=10, cost=1_000, aliases=15)).mount(app)
```

## What is measured

| | default | |
|---|---|---|
| `depth` | 10 | Deepest field nesting |
| `cost` | 1000 | Weighted complexity; `None` disables it |
| `aliases` | 15 | Most aliases of one field in a selection set |
| `breadth` | 100 | Largest selection set |
| `max_tokens` | 5000 | Document tokens, applied while parsing |
| `list_multiplier` | 10 | Assumed page size when it is not knowable |
| `default_field_cost` | 1 | What a field costs when nothing says otherwise |

Each is checked independently, and the first one passed refuses the operation
with `OPERATION_TOO_COMPLEX` and the limit it exceeded — a client that is
refused should be able to fix its query without guessing.

```json
{
  "errors": [{
    "message": "Operation is deeper than the limit of 10",
    "extensions": { "code": "OPERATION_TOO_COMPLEX", "limit": 10 }
  }]
}
```

## Why four structural limits and not just depth

They catch different shapes of the same attack.

**Depth** catches recursion. **Aliases** catch the query that is shallow and
enormous — `a: search b: search c: search` a hundred times over is depth 1.
**Breadth** catches one selection set asking for everything. **`max_tokens`**
catches the document that is expensive to parse before any of the above can
look at it.

Aliases are counted per selection set rather than per document, deliberately:
three here and three there is not the same thing as six of one field.

## Cost

Structure is a proxy. Cost is the measure that knows a list field multiplies
everything under it.

```graphql
{ users(first: 50) { posts(first: 20) { title } } }
```

That is 50 × 20 = 1000 titles from a query three levels deep. Depth alone
cannot see it.

The multiplier comes from the field's own page argument — `first`, `last`,
`limit`, `take`, `page_size`, `pageSize` — as an integer literal or an integer
variable. A caller asking for 5 is charged for 5. When the size is not
knowable, `list_multiplier` applies, which is the safe direction to be wrong
in.

Introspection meta-fields cost nothing: they are answered from the schema in
memory.

### Pricing a field

```python
@field(cost=25)
async def search(ctx: HttpContext, term: str) -> list[Hit]:
    ...
```

Or from outside, per type or by bare name:

```python
Graph(schema, costs={"Query.search": 25, "Post.renderedBody": 10})
graph.cost("search", 25)
```

A qualified `Type.field` wins over a bare name, so two types can price a field
of the same name differently.

### Choosing a budget

Measure rather than guess. Turn cost analysis off, run your client's real
operations, and read what they actually cost:

```python
graph = Graph(schema, limits=Limits(cost=None))   # measure, do not enforce
```

Every response then carries what it cost:

```json
{
  "data": { ... },
  "extensions": {
    "cost": { "depth": 4, "cost": 212, "aliases": 1, "breadth": 6, "fields": 11 }
  }
}
```

Take the largest legitimate operation, add headroom, and set that. A budget
derived from your own client is one you can defend; a round number is one you
will end up raising in an incident.

## Accuracy needs the schema

The analyser is given your schema, so it knows which fields return lists and
which do not. Without one, every field with a selection set is treated as a
list — which errs towards refusing large queries rather than allowing them, but
overstates the cost of an ordinary object traversal.

This is automatic. It is worth knowing because it explains why a cost can look
higher than you expect in a unit test that calls `analyze` without a schema.

## Introspection

Off by default, and separate from the limits.

```python
Graph(schema, introspection=True)      # for a development endpoint
```

An endpoint that publishes its own schema publishes every field an attacker
might try. Turning it off does not make a schema secret — a determined client
will guess field names — but it removes the map.

`__typename` is **not** introspection: it answers about the object in hand
rather than about the schema, and clients need it. Only `__schema` and `__type`
are refused.

## Measuring without enforcing

```python
from graphql import parse
from sillo.graphql import Limits, analyze

result = analyze(parse(document), limits=Limits(), schema=graph.schema._schema)
result.depth, result.cost, result.aliases, result.breadth, result.fields
```

Useful in a test that pins the cost of your client's real operations, so a
schema change that makes one ten times more expensive shows up as a failing
assertion rather than as a slow afternoon.

## Relaxing everything

```python
Graph(schema, limits=Limits.none())
```

For a trusted internal endpoint, and only one. `Limits.none()` is explicit
about what it is; passing large numbers by hand reads like a considered choice
rather than a decision to have no limit at all.

The stronger answer for a public endpoint is
[trusted documents](/packages/graphql/persisted/) — with a manifest in force,
the set of executable operations is finite and known, and the cost ceiling is
one you measured rather than guessed.
