---
title: Persisted Operations
description: APQ saves bandwidth; a trusted-document manifest makes the workload finite. Two different things that share one name.
---

Two things share this name, and only one of them is about safety.

**Automatic persisted queries** are a bandwidth optimisation. A client sends a
hash instead of the document; on a miss it is told so, sends the document once,
and the hash works from then on. Any document is still accepted.

**Trusted documents** are the safety property. A manifest of the operations
your application actually sends is generated at build time, and the server
executes nothing else.

```python
from sillo.graphql import Persisted

Graph(schema, persisted=Persisted(apq=True))                        # bandwidth
Graph(schema, persisted=Persisted(trusted="operations.json"))       # safety
Graph(schema, persisted=Persisted(apq=True, trusted="operations.json"))
```

## Automatic persisted queries

The protocol every Apollo client already speaks.

The client sends a hash:

```json
{ "extensions": { "persistedQuery": { "version": 1, "sha256Hash": "abc123…" } } }
```

On a miss it gets back `PERSISTED_QUERY_NOT_FOUND` and retries once with the
document attached. The server verifies that the hash matches the document —
**verified, not trusted**, or the store becomes a place to park arbitrary
documents under a chosen key — stores it, and answers the hash from then on.

```python
Persisted(apq=True, ttl=86_400, cache=None)
```

By default entries live in an in-process `MemoryStore`, bounded and evicting
oldest-first — an unbounded map keyed by client-supplied hashes is a memory
leak with a nice name. Across several processes each learns the same documents
separately, which is correct and merely wasteful, so a shared store is worth
configuring once there is more than one.

```python
from sillo.graphql import MemoryStore

Graph(schema, store=MemoryStore(max_entries=5_000))
```

Any object with `async get(key)` and `async set(key, document, ttl)` satisfies
the `PersistedStore` protocol — Redis, memcached, whatever you already run.

## Trusted documents

This is the one that changes what your endpoint is.

With a manifest in force the endpoint executes **only** the documents in it.
The consequences are worth listing, because together they are the difference
between an endpoint you can leave on the internet and one you cannot:

- the workload is finite and enumerable, so a cost ceiling is measured rather
  than guessed;
- arbitrary-query denial of service stops being possible at all;
- introspection stops mattering — knowing the schema buys nothing if no new
  query can be run;
- `GET` responses become safe to cache, because the set of possible responses
  is known.

```python
Graph(schema, persisted=Persisted(trusted="operations.json"))
```

The manifest is a JSON object of hash → document:

```json
{
  "8f3e…": "query Me { me { id email } }",
  "b21c…": "query Posts($first: Int!) { posts(first: $first) { id title } }"
}
```

Generate it from your client's operations at build time and ship it with the
server. It can also be passed inline, which is what a test wants:

```python
from sillo.graphql import hash_document

document = "{ hello }"
Graph(schema, persisted=Persisted(trusted={hash_document(document): document}))
```

### Sending one

A client sends the hash as `documentId`, or through the APQ extension:

```json
{ "documentId": "8f3e…", "variables": { "first": 10 } }
```

An unknown hash is refused with `OPERATION_NOT_PERMITTED`.

### Literal documents

A literal document is accepted only if its hash is in the manifest. That keeps
development tooling working against a manifest-enforcing endpoint without
widening what it will execute — the tool sends the whole document, and it runs
because it is one of the trusted ones.

Anything else is refused with `OPERATION_NOT_PERMITTED`, whatever it says.

## The codes

| | |
|---|---|
| `PERSISTED_QUERY_NOT_FOUND` | Unknown hash; the client should retry with the document. Expected, and part of the protocol |
| `PERSISTED_QUERY_NOT_SUPPORTED` | A hash arrived with APQ disabled |
| `OPERATION_NOT_PERMITTED` | A manifest is in force and this is not in it |
| `BAD_USER_INPUT` | The hash does not match the document supplied |

## Rolling it out

The order that avoids downtime:

1. Ship `apq=True`. Clients start sending hashes; nothing is refused.
2. Generate the manifest from the operations your clients actually send, from
   the APQ store or from a client build step.
3. Enable `trusted=` on a staging endpoint and run the client against it.
   Anything refused is an operation the manifest is missing.
4. Enable it in production.

Step 3 is the one not to skip. The failure mode is an operation nobody
remembered — an admin screen, a mobile version still in the field — and it
fails closed.

## Old clients in the field

A mobile release you cannot recall is the usual reason a manifest is
impossible. Two options: keep the union of every manifest still deployed, or
serve the older clients from a second `Graph` on its own path with looser
settings. The second is honest about what is going on and lets you watch the
old path's traffic go to zero.
