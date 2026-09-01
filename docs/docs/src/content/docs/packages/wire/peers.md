---
title: Peers & Backpressure
description: One connection, one bounded queue, one writer task — and what to do when a client stops reading.
---

A `Peer` is one connection: a socket, an outbound queue, and a task that drains
one into the other.

```python
from sillo.wire import Peer

peer = Peer(socket, identity="ada")
```

## Why there is a queue at all

The obvious way to broadcast is to await each socket in turn. It is also the
way that stops working under load, and it fails in the worst possible shape:
one client on a train, with a full TCP window and a socket that will not accept
another byte, holds up everyone else in the room behind it.

So a broadcast never touches a socket. It puts an envelope on each peer's queue
and returns. Each peer's writer task takes envelopes off its own queue and
writes them, at whatever pace its own socket allows. A slow client slows only
itself.

The queue is bounded — an unbounded one is not backpressure, it is a memory
leak that takes longer to notice.

## Construction

```python
Peer(
    socket,
    encoding=Encoding.JSON,
    identity=None,
    capacity=64,
    overflow=Overflow.DROP_OLDEST,
    idle_timeout=None,
)
```

**`encoding`** decides how payloads are written: `Encoding.JSON` (`send_json`),
`Encoding.TEXT` (`send_text`), `Encoding.BYTES` (`send_bytes`).

**`identity`** is whatever you use to mean a person — a user id, an email, a
tenant. It is the key [`send_to`](/packages/wire/hub/) matches on, and what
[presence](/packages/wire/presence/) reports. Leave it `None` for anonymous
connections.

**`capacity`** is how many envelopes may be waiting. 64 is a reasonable default
for chat-shaped traffic. Raise it for bursty feeds a client will catch up on;
lower it for high-rate streams where old data is worthless.

**`idle_timeout`** marks a peer idle after that many seconds without a write.
Nothing happens automatically — `is_idle()` reports it and your own reaper
decides.

## Overflow: what a full queue means

This is a choice about your data, and there is no default that is right for
everyone.

```python
from sillo.wire import Overflow, Peer

Peer(socket, overflow=Overflow.DROP_OLDEST)   # keep current
Peer(socket, overflow=Overflow.DROP_NEWEST)   # keep order
Peer(socket, overflow=Overflow.CLOSE)         # give up on the client
```

**`DROP_OLDEST`** discards the front of the queue to make room. The client sees
the most recent state and a gap in the middle. Right for prices, cursors,
telemetry, dashboards — anything where the newest value supersedes the last.

**`DROP_NEWEST`** refuses the incoming envelope and keeps what is queued. The
client sees an unbroken prefix and then a gap at the end. Right for anything
order-dependent that will be reconciled later — an event log the client
replays, a chat that will fetch history on reconnect.

**`CLOSE`** closes the peer. Right when falling behind means the client is
broken or hostile, and reconnecting from a clean state is cheaper than catching
up.

Whichever you pick, the count comes back in the broadcast's
[`DeliveryReport`](/packages/wire/reference/) as `dropped`. A room that reports
drops every second is telling you the capacity or the policy is wrong.

## Sending

```python
await peer.send({"msg": "hello"})     # enqueue, or apply the overflow policy
peer.offer(envelope)                  # the same, without building an envelope
```

`send` is what application code wants. `offer` is what the hub calls — it takes
an already-built envelope so one broadcast constructs one object rather than
one per member. Neither blocks on the socket; both return once the envelope is
queued or dropped.

## Lifecycle

```python
peer.start()          # begin draining; idempotent
await peer.close()    # stop the writer, close the socket
peer.closed           # bool
peer.pending          # envelopes waiting to be written
peer.is_idle()        # against idle_timeout
```

`hub.join` calls `start()` for you. Call it yourself only for a peer that is
not in any room.

`close` is safe to call twice, and safe to call on a socket that has already
gone away — a disconnect racing a shutdown produces exactly that.

## Reaping idle connections

`idle_timeout` reports; it does not act. What to do about an idle connection is
application policy — a dashboard that sends nothing for an hour is healthy, a
chat that does is probably a dead tab.

```python
peer = Peer(socket, idle_timeout=300)

async def reap():
    while True:
        await asyncio.sleep(60)
        for candidate in hub.members("lobby"):
            if candidate.is_idle():
                await hub.disconnect(candidate)
```

## Watching for backpressure

`pending` is the honest health signal for a realtime backend. A peer whose
`pending` sits near `capacity` is one that will start dropping.

```python
@app.get("/health/sockets")
async def sockets(ctx):
    peers = hub.members("lobby")
    return json({
        "peers": len(peers),
        "worst_queue": max((p.pending for p in peers), default=0),
        "capacity": 64,
    })
```
