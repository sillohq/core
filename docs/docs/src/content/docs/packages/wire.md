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

## Why it is a separate package

It was `sillo.websockets.channels` until v1. It moved for a dependency
direction rather than for size: the room layer needs a socket, a socket needs
nothing from the room layer, and fan-out is the part that grows a backend —
Redis or NATS, when groups have to span more than one worker process. That
belongs behind its own install rather than in everyone's core.

## What changed in the move

Three things the original could not do, and they are the reason the rewrite was
worth it rather than a rename.

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

The old history also sized itself with `sys.getsizeof` on a list, which
measures the pointer array rather than the messages — a "1 MB" cap held about a
hundred times that, and cleared everything when it finally tripped. Retention
is now counted in payload bytes and evicts oldest-first.

## Slow consumers

What happens when a peer cannot keep up is a choice, not a default:

```python
from sillo.wire import Overflow, Peer

Peer(socket, overflow=Overflow.DROP_OLDEST)   # keep current — prices, cursors
Peer(socket, overflow=Overflow.DROP_NEWEST)   # keep order — reconcile later
Peer(socket, overflow=Overflow.CLOSE)         # disconnect; let it reconnect
```

## Presence and identity

Two peers can share an identity — one person with a phone and two tabs — and
`send_to` reaches all of them:

```python
@hub.on_join
async def joined(room, peer):
    await hub.broadcast(room, {"event": "joined", "who": peer.identity})

hub.identities("lobby")                    # ["ada", "bob"] — people, not sockets
await hub.send_to("ada", {"notice": "your export is ready"})
```

## Consumers

`RoomConsumer` is the class-based form. It accepts the socket, builds the peer,
joins the rooms, pumps messages, and guarantees the peer leaves every room when
the connection ends — including when a hook raises.

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

## Testing

`sillo.wire.testing` ships the piece a unit test of realtime code is missing —
a socket:

```python
from sillo.wire import Hub, Peer
from sillo.wire.testing import FakeSocket, drain

async def test_a_broadcast_reaches_the_room():
    hub, socket = Hub(), FakeSocket()
    peer = Peer(socket)
    await hub.join(peer, "lobby")

    await hub.broadcast("lobby", {"hello": True})
    await drain(peer)          # broadcasts enqueue; this waits for the write

    assert socket.sent == [{"hello": True}]
```

`FakeSocket(delay=…)` is a client that reads slowly and `FakeSocket(fail=True)`
one that has gone away — the two cases hardest to reproduce against a real
server, and the two most worth testing.

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
`broadcast` returns a `DeliveryReport`.

## Source

[github.com/sillohq/wire](https://github.com/sillohq/wire) — BSD-3-Clause,
Python 3.10+, no dependencies beyond `sillo-framework`.
