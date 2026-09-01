---
title: Presence
description: Who is in the room — identity, join and leave listeners, and reaching a person rather than a socket.
---

A socket is not a person. One person with a laptop and a phone, and a second
tab open on each, is four sockets. Presence is the difference between those two
counts.

## Identity

```python
peer = Peer(socket, identity=user.id)
```

`identity` is whatever you mean by "who" — a user id, an email, a tenant. Two
peers may share one, and that is the normal case rather than an edge case.

Leave it `None` for anonymous connections. `None` identities are dropped from
`identities()` rather than reported as a person called nothing.

## Listeners

```python
@hub.on_join
async def joined(room, peer):
    await hub.broadcast(room, {
        "event": "joined",
        "who": peer.identity,
        "count": hub.count(room),
    }, retain=False)


@hub.on_leave
async def left(room, peer):
    await hub.broadcast(room, {
        "event": "left",
        "who": peer.identity,
        "count": hub.count(room),
    }, retain=False)
```

Both decorators return the function, so they stack with anything else and the
name stays usable.

Listeners fire for every room a peer joins or leaves — including the several
rooms `disconnect` and `leave_all` unwind at once.

**`retain=False` matters here.** A presence event is only true at the moment it
is sent. Retaining it means a client that connects ten minutes later replays
"ada joined" for someone who has since gone, and now shows a room that does not
exist.

### The mistake worth avoiding

A joining peer is already a member when its `on_join` listener runs, so an
unqualified broadcast reaches it too — and a client that has just connected
receives an announcement of its own arrival. Usually you want it; when you do
not, address the others directly:

```python
@hub.on_join
async def joined(room, peer):
    for other in hub.members(room):
        if other is not peer:
            await other.send({"event": "joined", "who": peer.identity})
```

## Counting

```python
hub.identities("lobby")    # ["ada", "bob"] — people, deduplicated
hub.members("lobby")       # [Peer, Peer, Peer] — sockets
hub.count("lobby")         # 3 — sockets, not people
hub.count()                # distinct peers across every room
```

`len(hub.identities(room))` is the number your UI means when it says "3
online". `hub.count(room)` is the number your dashboard means when it says
"3 connections". They are rarely equal and it matters which one you show.

## Reaching a person

```python
report = await hub.send_to("ada", {"notice": "your export is ready"})
report.delivered   # 3 — laptop, phone, and that tab she forgot
```

`send_to` matches on identity across every room in the hub, so a notification
reaches someone wherever they happen to be connected. An identity nobody is
connected under returns a report of zeroes rather than raising — the user is
offline, which is not an error.

Identity comparison is `==`, so anything hashable works. Keep it stable: a
tuple of `(tenant, user_id)` is fine, an object without `__eq__` is not.

## Presence that survives a refresh

Listeners fire on socket lifecycle, and a page refresh is a disconnect followed
by a connect. Broadcasting both events makes a refresh look like someone
leaving and a stranger arriving.

If that matters, debounce on identity rather than on peer — leave is only real
if that identity has no peers left a moment later:

```python
@hub.on_leave
async def left(room, peer):
    await asyncio.sleep(2)
    if peer.identity not in hub.identities(room):
        await hub.broadcast(room, {"event": "left", "who": peer.identity},
                            retain=False)
```

## Cleaning up peers nobody closed

A socket that dies without a clean close leaves its peer in its rooms until
something notices. Broadcasts to it count as `failed` rather than raising, so
nothing breaks — but presence counts drift upward.

```python
@app.on_startup
async def reaper():
    async def loop():
        while True:
            await asyncio.sleep(30)
            await hub.prune()
    asyncio.create_task(loop())
```

`prune` removes closed peers and returns them, firing the leave listeners on
the way out — so presence corrects itself rather than needing a separate sweep.
