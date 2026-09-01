---
title: Subscriptions
description: graphql-transport-ws over the framework's own WebSocket layer, authentication in connection_init, and the SSE fallback.
---

```python
from typing import AsyncGenerator

import strawberry
from sillo import WebSocketContext
from sillo.graphql import subscription


@strawberry.type
class Subscription:
    @subscription
    async def prices(ctx: WebSocketContext, symbol: str) -> AsyncGenerator[Price, None]:
        async for tick in feed(symbol):
            yield tick


Graph(strawberry.Schema(query=Query, subscription=Subscription)).mount(app)
```

A WebSocket route is mounted on the same path as the HTTP one. Nothing else is
required.

**Subscriptions are mounted only if the schema declares a subscription type.**
The framework's old module served an explorer that advertised a socket which
did not exist; a page offering an endpoint the server does not serve is worse
than no page.

```python
Graph(schema, subscriptions=False)     # or turn them off explicitly
```

## The protocol

`graphql-transport-ws`, negotiated through `Sec-WebSocket-Protocol`.

1. The client connects and sends `connection_init`; the server replies
   `connection_ack`.
2. Each operation is a `subscribe` carrying an id. The server answers with
   `next` messages and ends with `complete` or `error`.
3. Either side may `ping`; the other answers `pong`.
4. The client sends `complete` with an id to unsubscribe.

Three rules do most of the work of keeping it well behaved:

- a connection that never sends `connection_init` is closed after
  `init_timeout` seconds, so an idle socket cannot hold a slot for free;
- an id already in use closes the connection, because the alternative is two
  operations racing over one channel;
- **every operation is cancelled when its socket closes**, in a `finally`. A
  subscription that outlives its client is a leak that compounds.

That last one is why a subscription holding a database session must release it
in a `finally` — cancellation raises at the `yield`.

```python
@subscription
async def prices(symbol: str, db=Depend(get_db)) -> AsyncGenerator[Price, None]:
    async for tick in db.stream(symbol):
        yield tick
    # `Depend` teardown runs on unsubscribe and on disconnect alike.
```

## Authenticating a socket

A browser cannot set headers on a WebSocket handshake, so a token arrives in
the `connection_init` payload instead. `@graph.on_connect` is given it before
any operation runs.

```python
from sillo.graphql import unauthenticated


@graph.on_connect
async def authenticate(socket, params):
    token = params.get("authorization")
    user = await user_for(token) if token else None
    if user is None:
        raise unauthenticated("A valid token is required")
    return {"user": user}
```

Raising closes the connection with 4401. Whatever is returned is merged into
the context's `extra`, and the raw payload is available as
`extra["connection_params"]`.

```python
@field
async def me(context: GraphContext) -> User:
    return context.extra["user"]
```

Hooks may be sync or async and stack. This is the right place for
authentication — a per-field check would run after the socket is already open
and counted.

## Close codes

| | |
|---|---|
| 4400 | Malformed message, or an unknown type |
| 4401 | Subscribed before `connection_init`, or `on_connect` refused |
| 4408 | `connection_init` never arrived in time |
| 4409 | An operation id already in use |
| 4429 | `connection_init` sent twice |

## Tuning

```python
from sillo.graphql.transport.ws import WebSocketTransport

graph.ws = WebSocketTransport(graph, init_timeout=5.0, keepalive=20.0)
```

`init_timeout` bounds how long an unauthenticated socket may say nothing.
Lower it on a public endpoint.

## Queries over the socket

The protocol carries queries and mutations too, and this transport serves them:
a `subscribe` message with a query document answers one `next` and then
`complete`. A client that has a socket open need not also open an HTTP request.

They pass through the same [limits](/packages/graphql/limits/),
[persisted-document rules](/packages/graphql/persisted/) and
[error policy](/packages/graphql/errors/) as they would over HTTP. That
consistency is why those decisions live on the `Graph` rather than in a
transport.

## Server-sent events

A WebSocket is the right transport for subscriptions and is not always
available: corporate proxies drop them, some platforms do not offer them, and
an `EventSource` is far less for a client to carry.

```python
Graph(schema, sse=True)
```

The framing is the GraphQL-over-SSE specification's *distinct connections
mode*: one request opens one stream for one operation, `next` events carry each
result, and a `complete` event ends it.

```
event: next
data: {"data":{"prices":{"last":10}}}

event: next
data: {"data":{"prices":{"last":11}}}

event: complete
data: {}
```

There is no `connection_init` handshake, because the request is an ordinary
HTTP request and carries its own headers — which is the other reason to reach
for this transport.

An error before or during execution is delivered **on the stream** rather than
as a status: the response headers went out with the first byte, so there is no
status left to change.

The response sets `cache-control: no-cache` and `x-accel-buffering: no`. A
proxy that buffers defeats the point of streaming, and nginx reads that second
header.

## Broadcasting to subscribers

A subscription resolver is an async generator; where its values come from is
yours. The natural pairing is [`sillo-wire`](/packages/wire/), which already
holds rooms of connections:

```python
@subscription
async def room_events(ctx: WebSocketContext, room: str) -> AsyncGenerator[Event, None]:
    queue: asyncio.Queue[Event] = asyncio.Queue()
    subscribers[room].add(queue)
    try:
        while True:
            yield await queue.get()
    finally:
        subscribers[room].discard(queue)
```

The `finally` is the part not to skip: without it, a client that disconnects
leaves its queue in the set, and every later publish grows a structure nobody
reads.
