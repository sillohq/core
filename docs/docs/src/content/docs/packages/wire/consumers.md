---
title: Consumers
description: RoomConsumer — the class-based form, with accept, join, the read loop and cleanup already written.
---

The function form of a socket handler is four lines of ceremony around one line
of application code, and the ceremony is where the leaks are. `RoomConsumer`
writes it once.

```python
from sillo.wire import Hub, RoomConsumer

hub = Hub()


class Chat(RoomConsumer):
    hub = hub

    async def identify(self, ctx):
        return ctx.query_params.get("user")

    async def rooms(self, ctx):
        return [ctx.path_params["room"]]

    async def on_message(self, data):
        await self.broadcast({"from": self.peer.identity, "text": data})


app.add_ws_route(path="/ws/{room}", handler=Chat.as_handler())
```

## What it does for you

In order, per connection:

1. accepts the socket;
2. calls `identify(ctx)` and builds a [`Peer`](/packages/wire/peers/) with the
   class's `encoding`, `capacity` and `overflow`;
3. calls `rooms(ctx)` and joins each one;
4. calls `on_connect()`;
5. reads from the socket, calling `on_message(data)` per message, until it
   closes;
6. **in a `finally`**, calls `on_disconnect()` and then `hub.disconnect(peer)`.

Step 6 is the reason to use it. It runs on a clean close, on a client vanishing
mid-message, and on one of your own hooks raising. A peer left subscribed after
its socket is gone is the leak that makes presence counts drift and broadcast
reports fill with `failed`.

A fresh instance is created per connection, so `self` is a safe place for
per-connection state — unlike the hub, which is shared by all of them.

## Configuration

Four class attributes, all optional except the hub:

```python
class Feed(RoomConsumer):
    hub = hub
    encoding = Encoding.JSON        # JSON | TEXT | BYTES
    capacity = 256                  # outbound queue depth
    overflow = Overflow.DROP_OLDEST # what a full queue means
```

`encoding` picks both how payloads are written and which `iter_*` the read loop
uses, so the two can never disagree.

The hub can also come in at registration, which is what you want when one
consumer class serves two hubs:

```python
app.add_ws_route(path="/ws/{room}", handler=Chat.as_handler(hub=tenant_hub))
```

A consumer with no hub on the class and none passed raises `ValueError` at
construction, naming the class — better than a `None` that surfaces four frames
later.

## Hooks

```python
async def identify(self, ctx) -> Any: ...        # -> the peer's identity
async def rooms(self, ctx) -> list[str]: ...     # -> rooms to join
async def on_connect(self) -> None: ...          # after joining
async def on_message(self, data) -> None: ...    # per message
async def on_disconnect(self) -> None: ...       # always
```

`identify` and `rooms` are given the context, so they can read path parameters,
query parameters, headers and `ctx.user`. The other three are not: they run
after `self.ctx` and `self.peer` are set, and reaching them through `self` keeps
every subclass from having to declare parameters it does not use.

Path parameters reach `as_handler`'s route as keyword arguments, exactly as on
an HTTP route, and are available as `ctx.path_params`.

## Helpers

```python
await self.broadcast(payload)                # to the first room joined
await self.broadcast(payload, room="ops")    # to a named one
await self.reply(payload)                    # to this connection only
await self.join("support")                   # join another room mid-connection
await self.leave("support")
```

`self.joined` is the list of rooms in join order, which is what `broadcast`
defaults to the first of. `self.peer` is the `Peer`, and `self.ctx` the socket
context.

## Authentication

`identify` is the natural gate. Raising from it means the socket is accepted and
then closed, which is the correct protocol behaviour — a WebSocket handshake
cannot carry a 401 body.

```python
class Private(RoomConsumer):
    hub = hub

    async def identify(self, ctx):
        user = await authenticate(ctx.headers.get("authorization"))
        if user is None:
            await ctx.close(code=4401, reason="Unauthorized")
            raise ConnectionError("unauthenticated")
        return user.id
```

Cleanup still runs: the `finally` is outside the hooks, so a raising `identify`
disconnects cleanly rather than leaving a half-built peer behind.

## When to use the function form instead

`RoomConsumer` assumes one read loop dispatching messages one at a time. A
handler that wants two concurrent tasks over one socket — a reader and an
independent ticker — is clearer written out:

```python
@app.ws_route("/ws/prices/{symbol}")
async def prices(socket, symbol: str):
    await socket.accept()
    peer = Peer(socket)
    await hub.join(peer, symbol)
    try:
        await asyncio.gather(read_orders(socket), stream_ticks(peer, symbol))
    finally:
        await hub.disconnect(peer)
```

The `finally` is the part not to skip. Everything `RoomConsumer` does for you
is available directly; it is the guarantee that is easy to forget.
