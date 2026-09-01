---
title: The Hub
description: Rooms, membership and fan-out — join, leave, broadcast, send_to, and why a Hub is an object rather than a global.
---

A `Hub` is a set of rooms, and a room is a set of peers. Everything that
reaches more than one connection goes through it.

```python
from sillo.wire import Hub

hub = Hub()
```

## It is an object, deliberately

The predecessor was a class with class methods over a process-wide dictionary.
Two consequences followed from that and neither was wanted: tests shared state
with each other, and two tenants in one process could not be kept apart.

Two hubs are two independent worlds. Nothing is registered anywhere, so a hub
created in a test is collected with the test.

```python
tenants = {name: Hub() for name in ("acme", "globex")}
await tenants["acme"].broadcast("lobby", {"msg": "only acme sees this"})
```

Most applications have exactly one, defined at module scope beside the app.

## Membership

```python
await hub.join(peer, "lobby")     # True if newly added
await hub.leave(peer, "lobby")    # True if it was a member
await hub.leave_all(peer)         # -> ["lobby", "support"]
await hub.disconnect(peer)        # leave everything, then close the socket
```

`join` starts the peer's writer task if it is not already running, so you never
have to remember to. An empty room name raises `ValueError` — a room named `""`
is a bug that otherwise stays invisible until nobody receives anything.

`leave` on a room the peer is not in is **not** an error. A disconnect racing a
cleanup produces exactly that, routinely, and raising would turn a normal race
into a log full of tracebacks.

`disconnect` is what a `finally` block wants: it leaves every room, fires the
leave listeners, and closes the peer.

```python
try:
    async for message in socket.iter_json():
        await hub.broadcast(room, message)
finally:
    await hub.disconnect(peer)
```

## Fan-out

```python
report = await hub.broadcast("lobby", {"msg": "hello"})
```

Every member's queue is offered the same [`Envelope`](/packages/wire/reference/),
concurrently. The call does not wait for any socket to accept it — that is the
point, and it is what stops one stalled client from holding up forty others.

What comes back says what happened:

```python
report.delivered   # queued for writing
report.dropped     # queue was full; see the overflow policy
report.failed      # peer was already closed
report.attempted   # the sum of the three
```

A room nobody is in is not an error. `broadcast` returns a report of zeroes,
and — unless you say otherwise — the message still goes to the backlog, so a
client that joins in a moment can replay it.

```python
await hub.broadcast("lobby", {"typing": "ada"}, retain=False)
```

`retain=False` keeps a message out of the backlog. Use it for anything whose
value expires: typing indicators, cursor positions, presence churn. Replaying
"ada is typing" to someone who connects four minutes later is worse than
sending nothing.

### Reaching a person rather than a room

```python
await hub.send_to("ada", {"notice": "your export is ready"})
```

`send_to` delivers to every peer with that `identity`, across every room — one
person with a phone and two tabs is three peers and one identity. It returns
the same `DeliveryReport`. See [Presence](/packages/wire/presence/).

## Inspecting

```python
hub.rooms()                # ["lobby", "support"]
hub.members("lobby")       # [Peer, Peer, ...]
hub.identities("lobby")    # ["ada", "bob"] — deduplicated, Nones dropped
hub.count("lobby")         # 12
hub.count()                # every distinct peer in the hub
```

All four are synchronous and return snapshots — plain lists you can iterate
without holding anything.

## Housekeeping

```python
await hub.prune()          # remove closed peers; returns the ones removed
await hub.close()          # close every peer and empty every room
```

A peer whose socket closed without a `disconnect` stays in its rooms until
something notices. Broadcasts to it count as `failed` rather than raising, so
nothing breaks — but the membership counts drift. `prune` is what a periodic
task calls to tidy that up.

`close` is for shutdown. It clears the rooms first and then closes every peer
**concurrently**: closing a thousand sockets one after another makes shutdown
as slow as the slowest one.

```python
@app.on_shutdown
async def stop():
    await hub.close()
```

## Presence hooks

```python
@hub.on_join
async def joined(room, peer):
    await hub.broadcast(room, {"event": "joined", "who": peer.identity},
                        retain=False)
```

Covered in full under [Presence](/packages/wire/presence/).

## History

A hub with a backlog can answer what a room has recently seen, and replay it
into a reconnecting peer.

```python
await hub.history("lobby", limit=50)          # newest 50 envelopes
await hub.replay(peer, "lobby", since=1042)   # -> how many were sent
await hub.clear_history("lobby")              # or clear_history() for all
```

See [Backlog & Replay](/packages/wire/backlog/).
