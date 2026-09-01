---
title: Observability
description: Per-operation metrics, slow-operation logs and OpenTelemetry spans — because p99 on POST /graphql means nothing.
---

One GraphQL path carries every operation an application performs, so the usual
HTTP signals say almost nothing. `p99` on `POST /graphql` is an average over
work that has nothing in common: a session check and a report that scans a
year of rows are the same endpoint.

What is worth measuring is per **operation**.

```python
from sillo.graphql import Metrics, OperationLog

graph.on_operation(OperationLog(slower_than=0.5))

metrics = Metrics()
graph.on_operation(metrics)
```

Nothing here is on by default, and nothing is in the request path unless it was
asked for.

## The hook

`@graph.on_operation` runs after every operation with the result and the
context.

```python
@graph.on_operation
async def observe(result, context):
    if result.errors:
        await alert(context.operation_name, result.errors)
```

| | |
|---|---|
| `result.data` | The data, or `None` |
| `result.errors` | Formatted errors |
| `result.ok` | Whether there were none |
| `context.operation_name` | The operation, named |
| `context.cost` | Its measured cost |
| `context.started` | When it began, on the monotonic clock |

Hooks may be sync or async, and stack.

### Naming

`operation_name` comes from the request, and falls back to the document when it
holds exactly one named operation — clients rarely send `operationName` for a
single query, and metrics keyed on `null` are no use.

Which is the argument for naming your operations. `query Me { ... }` gives you
a row in a dashboard; `{ me { ... } }` gives you a row called `anonymous`
shared with everything else unnamed.

## Metrics

Counters held in memory, deliberately not a Prometheus client — this collects,
and your application exports however it already exports things.

```python
metrics = Metrics()
graph.on_operation(metrics)


@app.get("/metrics")
async def show(ctx):
    return json(metrics.snapshot())
```

```json
{
  "Me":    { "count": 4821, "errors": 3, "average_seconds": 0.004,
             "slowest_seconds": 0.09, "average_cost": 6 },
  "Posts": { "count": 190,  "errors": 0, "average_seconds": 0.21,
             "slowest_seconds": 2.8,  "average_cost": 212 }
}
```

Durations are kept as a running total rather than a list — an endpoint serving
a few hundred operations a second would otherwise accumulate unbounded memory
in the name of observing itself. That means no true percentiles; `slowest` is
the tail signal available. Export to something that does histograms if you need
p99.

`reset()` clears it, for a scrape-and-reset collector.

## Logging the slow ones

```python
graph.on_operation(OperationLog(slower_than=0.5))
```

```
WARNING sillo.graphql.operations graphql Posts 2841.3ms cost=212 errors=1
```

`slower_than=0` logs everything, which a development log wants and a production
one does not. Operations that produced errors are logged whatever their
duration, unless `errors=False`.

Pass a logger of your own as the first argument; it defaults to
`sillo.graphql.operations`.

## OpenTelemetry

```python
from opentelemetry import trace
from sillo.graphql import opentelemetry

graph.on_operation(opentelemetry(trace.get_tracer("graphql")))
```

One span per operation, with `graphql.operation.name`, `graphql.errors` and
`graphql.cost`.

The span is created after the fact with an explicit start time taken from the
context — the hook runs when the operation finishes, and back-dating it is what
keeps its duration honest rather than zero.

This package does not depend on OpenTelemetry. An application that uses it
already has a tracer to hand, and one that does not should not carry the
dependency.

## Cost in the response

Every response carries what it cost, when cost analysis is on:

```json
{ "extensions": { "cost": { "depth": 4, "cost": 212, "aliases": 1,
                            "breadth": 6, "fields": 11 } } }
```

Useful during development and while
[choosing a budget](/packages/graphql/limits/). It is also visible to clients —
if that matters, run with `Limits(cost=None)` in production and keep the
enforcement structural.

## What to watch

**`average_cost` rising** for an operation nobody changed means the client
changed: a new field, a larger page size. It is the earliest warning that a
query is about to become a problem.

**`errors` on one operation only** is usually a resolver, not the endpoint.
The correlation id in each error joins it to a log line — see
[Errors](/packages/graphql/errors/).

**`slowest` far above `average`** on an operation with a loader in it is the
signature of a batch that did not batch: a resolver awaiting something before
calling the loader lands in a later tick and batches alone. See
[Loaders](/packages/graphql/loaders/).
