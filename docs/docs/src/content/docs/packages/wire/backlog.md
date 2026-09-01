---
title: Backlog & Replay
description: What a reconnecting client missed — monotonic sequences, a byte-capped memory backlog, and the protocol for putting it somewhere else.
---

Mobile clients disconnect. Laptops sleep. A backlog is what turns that from
data loss into a gap the client can ask about.

```python
from sillo.wire import Hub, MemoryBacklog

hub = Hub(backlog=MemoryBacklog(capacity_bytes=4 * 1024 * 1024))
```

## Envelopes carry a sequence

Every broadcast becomes an `Envelope`, and every envelope gets a **monotonic**
`seq` — increasing across the whole process, never reused.

```python
@dataclass(frozen=True)
class Envelope:
    payload: Any
    room: str
    seq: int
    sent_at: datetime
```

Monotonic across the process rather than per room is deliberate: a client in
three rooms tracks one number instead of three, and `seq` values from different
rooms still sort into the order they were sent.

The client's job is to remember the last `seq` it saw. That is the whole
protocol.

## Replaying

```python
sent = await hub.replay(peer, "lobby", since=1042)
```

Everything in `lobby` after sequence 1042 is offered to that one peer, in
order, and the count comes back. `since=0` — the default — replays everything
retained.

A typical reconnect:

```python
@app.ws_route("/ws/room/{name}")
async def room(socket, name: str):
    await socket.accept()
    peer = Peer(socket, identity=socket.query_params.get("user"))
    await hub.join(peer, name)

    # The client tells us where it got to; 0 means "I am new".
    since = int(socket.query_params.get("since", 0))
    await hub.replay(peer, name, since=since, limit=200)
    ...
```

`limit` caps the catch-up. A client that has been away for a day should not be
handed a day of messages through a queue sized for live traffic — cap the
replay and let it fetch the rest over HTTP, where pagination already exists.

## Reading history without a peer

```python
recent = await hub.history("lobby", limit=50)
for envelope in recent:
    print(envelope.seq, envelope.payload)
```

Newest first, capped by `limit`. This is what an HTTP endpoint uses to render
the last few messages when a page loads, before its socket connects.

## Keeping things out of it

```python
await hub.broadcast("lobby", {"typing": "ada"}, retain=False)
```

Anything whose value expires should not be retained. Replaying "ada is typing"
to a client that connects four minutes later is worse than sending nothing at
all — it is wrong, and the client has no way to know.

Presence events are the usual case, and the reason `on_join` broadcasts in the
examples all pass `retain=False`.

## MemoryBacklog

The default, and enough for one process.

```python
MemoryBacklog(capacity_bytes=1024 * 1024)   # 1 MiB, the default
```

**The cap is on payload bytes**, not on message count and not on
`sys.getsizeof`. The predecessor measured a list with `getsizeof`, which
returns the size of the pointer array rather than of anything the pointers
lead to — a "1 MB" history held roughly 128 MB in practice, and then cleared
itself entirely when it finally tripped.

Eviction is oldest-first and incremental. Room by room:

```python
backlog = MemoryBacklog()
hub = Hub(backlog=backlog)

backlog.usage("lobby")     # bytes currently retained for that room
backlog.rooms()            # every room with anything retained
backlog.clear("lobby")     # or clear() for all of them
```

### Sizing it

Multiply your average payload by how far back a reconnecting client should be
able to reach. A chat with 400-byte messages at 5/second, wanting a two-minute
window, needs about 240 KB — so a 1 MiB default is already generous. A
telemetry stream at 50/second wants either far more, or `retain=False` and no
backlog at all.

## No backlog

```python
from sillo.wire import Hub, NullBacklog

hub = Hub(backlog=NullBacklog())    # the same as Hub()
```

`NullBacklog` accepts everything and remembers nothing. It exists so the hub
never has to check whether a backlog is present, and so `Hub()` and
`Hub(backlog=NullBacklog())` are the same thing rather than two code paths.

## Putting it somewhere else

`Backlog` is a `Protocol`, not a base class — an application that already has
Redis should be able to hand it over without inheriting anything.

```python
class Backlog(Protocol):
    def append(self, envelope: Envelope) -> None: ...
    def since(self, room: str, seq: int) -> list[Envelope]: ...
    def latest(self, room: str, limit: int = 50) -> list[Envelope]: ...
    def clear(self, room: str | None = None) -> None: ...
```

Four methods. A Redis implementation is a sorted set per room keyed by `seq`,
with `since` as `ZRANGEBYSCORE` and `latest` as `ZREVRANGE`:

```python
class RedisBacklog:
    def __init__(self, redis, *, prefix="wire", keep=1000):
        self.redis, self.prefix, self.keep = redis, prefix, keep

    def append(self, envelope):
        key = f"{self.prefix}:{envelope.room}"
        self.redis.zadd(key, {dumps(envelope): envelope.seq})
        self.redis.zremrangebyrank(key, 0, -self.keep - 1)

    def since(self, room, seq):
        raw = self.redis.zrangebyscore(f"{self.prefix}:{room}", f"({seq}", "+inf")
        return [loads(item) for item in raw]
    ...
```

Note what a shared backlog does **not** buy you: a broadcast still only reaches
peers connected to *this* process. Spanning processes needs a transport as well
— that is the next thing this package will grow, and it is why it is a separate
package at all.
