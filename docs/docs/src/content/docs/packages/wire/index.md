---
title: Wire
description: "sillo-wire — rooms, presence and fan-out for Sillo WebSockets: bounded queues, a replayable backlog, and no global state."
---

Rooms, presence and fan-out for WebSockets.

```bash
pip install sillo-wire
```

Installs as `sillo-wire`, imports as `sillo.wire`. The core keeps the socket
itself — [`WebSocketContext`](/v1.0/guides/websockets/) — and this adds
everything about talking to more than one of them at a time.

```python
from sillo import SilloApp
from sillo.wire import Hub, Peer

app = SilloApp()
hub = Hub()

@app.ws_route("/ws/room/{name}")
async def room(socket, name: str):
    await socket.accept()
    peer = Peer(socket, identity=socket.query_params.get("user"))
    await hub.join(peer, name)
    try:
        async for message in socket.iter_json():
            await hub.broadcast(name, message)
    finally:
        await hub.disconnect(peer)
```

## The shape of it

Four objects, and you will use two of them.

| | |
|---|---|
| [`Hub`](/packages/wire/hub/) | Rooms, and everything that fans out to them |
| [`Peer`](/packages/wire/peers/) | One connection, with a bounded outbound queue |
| [`Backlog`](/packages/wire/backlog/) | What a reconnecting client missed |
| [`RoomConsumer`](/packages/wire/consumers/) | The class-based form, with cleanup handled |

A `Peer` wraps a socket. A `Hub` holds sets of peers under room names. A
broadcast hands one `Envelope` to every peer's queue and returns immediately;
each peer's own writer task drains its queue to its socket. Nothing else is
going on.

## Why it is a separate package

It was `sillo.websockets.channels` until v1. It moved for a dependency
direction rather than for size: the room layer needs a socket, a socket needs
nothing from the room layer, and fan-out is the part that grows a backend —
Redis or NATS, when rooms have to span more than one worker process. That
belongs behind its own install rather than in everyone's core.

## What changed in the move

Three things the original could not do, and the reason this was a rewrite
rather than a rename.

**A broadcast no longer blocks on the slowest client.** The old fan-out awaited
each socket in turn, so one client that had stopped reading stalled every other
member of the group behind it. Every peer now has a bounded queue and a writer
task, so a broadcast only enqueues — and tells you what happened:

```python
report = await hub.broadcast("lobby", {"msg": "hello"})
report.delivered   # 41
report.dropped     #  2   queues were full
report.failed      #  1   socket was already gone
```

**Nothing is global.** `ChannelBox` was class methods over a process-wide dict,
so tests shared state and two tenants could not be kept apart. A `Hub` is an
object; two of them are two independent worlds.

**History is replayable.** Envelopes carry a monotonic sequence, so a client
that reconnects asks for what it missed:

```python
await hub.replay(peer, "lobby", since=last_seq_the_client_saw)
```

The old history sized itself with `sys.getsizeof` on a list, which measures the
pointer array rather than the messages — a "1 MB" cap held about a hundred
times that, and cleared everything when it finally tripped. Retention is now
counted in payload bytes and evicts oldest-first.

## Migrating from `sillo.websockets`

| Was | Is |
|---|---|
| `ChannelBox.group_send(name, payload)` | `await hub.broadcast(name, payload)` |
| `ChannelBox.add_channel_to_group(ch, name)` | `await hub.join(peer, name)` |
| `ChannelBox.remove_channel_from_group(ch, name)` | `await hub.leave(peer, name)` |
| `Channel(websocket, payload_type="json")` | `Peer(socket, encoding=Encoding.JSON)` |
| `ChannelBox.show_history(name)` | `await hub.history(name)` |
| `ChannelBox.set_history_manager(m)` | `Hub(backlog=m)` |
| `WebSocketConsumer` | `RoomConsumer` |
| `ChannelBox.CHANNEL_GROUPS` | `hub.rooms()`, `hub.members(room)` |

The status enums are gone. `join` and `leave` return a plain `bool`, and
`broadcast` returns a [`DeliveryReport`](/packages/wire/reference/).

## The two import paths

`sillo.wire` and `sillo_wire` are the same module object, not two copies. The
code lives in the top-level `sillo_wire` package; a `.pth` shipped with the
distribution registers a meta-path finder at interpreter startup, and PEP 561
partial stubs serve type checkers, which never run import hooks.

Nothing is written into the framework's own `sillo/` directory. Two
distributions sharing one package directory goes wrong in both directions —
installing the framework from a checkout orphans whatever the other package
left in site-packages, and removing the framework leaves a directory standing
with no `__init__.py` in it.

## Requirements

Python 3.10 through 3.14, and `sillo-framework`. Nothing else.

## Source

[github.com/sillohq/wire](https://github.com/sillohq/wire) — BSD-3-Clause.
