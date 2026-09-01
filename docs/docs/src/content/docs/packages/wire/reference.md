---
title: API Reference
description: Every public name in sillo.wire — signatures, defaults and what each one returns.
---

Everything importable from `sillo.wire`. Types are as annotated in the package;
`Any` means the value is yours and the library only carries it.

## Hub

```python
Hub(backlog: Backlog | None = None)
```

| Method | Returns | |
|---|---|---|
| `await join(peer, room)` | `bool` | Newly added. Starts the peer's writer. Empty room name raises `ValueError` |
| `await leave(peer, room)` | `bool` | Was a member. Not an error if it was not |
| `await leave_all(peer)` | `list[str]` | Rooms actually left |
| `await disconnect(peer)` | `None` | Leave everything, then close the peer |
| `await broadcast(room, payload, *, retain=True)` | `DeliveryReport` | Fan out concurrently |
| `await send_to(identity, payload)` | `DeliveryReport` | Every peer with that identity, any room |
| `await replay(peer, room, *, since=0, limit=None)` | `int` | Envelopes offered |
| `await history(room, limit=50)` | `list[Envelope]` | Newest first |
| `await clear_history(room=None)` | `None` | One room, or all |
| `await prune()` | `list[Peer]` | Closed peers removed |
| `await close()` | `None` | Close every peer concurrently, empty every room |
| `on_join(listener)` | the listener | Decorator: `async (room, peer)` |
| `on_leave(listener)` | the listener | Decorator: `async (room, peer)` |
| `rooms()` | `list[str]` | Rooms with at least one member |
| `members(room)` | `list[Peer]` | Snapshot |
| `identities(room)` | `list[Any]` | Deduplicated; `None` dropped |
| `count(room=None)` | `int` | Peers in a room, or distinct peers in the hub |

The four inspection methods are synchronous.

## Peer

```python
Peer(
    socket,
    *,
    encoding: Encoding = Encoding.JSON,
    identity: Any = None,
    capacity: int = 64,
    overflow: Overflow = Overflow.DROP_OLDEST,
    idle_timeout: float | None = None,
)
```

| Member | Returns | |
|---|---|---|
| `start()` | `None` | Begin draining. Idempotent; `hub.join` calls it |
| `await close()` | `None` | Stop the writer, close the socket. Safe twice |
| `await send(payload)` | `None` | Enqueue, or apply the overflow policy |
| `offer(envelope)` | `bool` | Accepted. Never blocks. What the hub calls |
| `is_idle(*, now=None)` | `bool` | Against `idle_timeout`; `False` when unset |
| `closed` | `bool` | property |
| `pending` | `int` | property — envelopes waiting |

## Envelope

```python
Envelope(payload: Any, room: str = "", seq: int = <next>, sent_at: datetime = <now>)
```

Frozen. `seq` is monotonic across the process, allocated on construction.
`size()` returns the payload's size in bytes, which is what the backlog's cap
counts.

## DeliveryReport

```python
DeliveryReport(delivered: int = 0, dropped: int = 0, failed: int = 0)
```

`attempted` is the sum. Returned by `broadcast` and `send_to`.

| | |
|---|---|
| `delivered` | Queued for writing |
| `dropped` | Queue was full; the overflow policy applied |
| `failed` | Peer was already closed |

## Overflow

What a full outbound queue means. See
[Peers & Backpressure](/packages/wire/peers/).

| | |
|---|---|
| `Overflow.DROP_OLDEST` | Discard the front. Keep current — prices, cursors |
| `Overflow.DROP_NEWEST` | Refuse the incoming. Keep order — event logs |
| `Overflow.CLOSE` | Close the peer. Let it reconnect clean |

## Encoding

How payloads are written, and which `iter_*` a consumer reads with.

| | |
|---|---|
| `Encoding.JSON` | `send_json` / `iter_json` |
| `Encoding.TEXT` | `send_text` / `iter_text` |
| `Encoding.BYTES` | `send_bytes` / `iter_bytes` |

## Backlog

A `Protocol`, so an existing store can satisfy it without inheriting anything.

```python
class Backlog(Protocol):
    def append(self, envelope: Envelope) -> None: ...
    def since(self, room: str, seq: int) -> list[Envelope]: ...
    def latest(self, room: str, limit: int = 50) -> list[Envelope]: ...
    def clear(self, room: str | None = None) -> None: ...
```

### MemoryBacklog

```python
MemoryBacklog(capacity_bytes: int = 1_048_576)
```

Capped on **payload bytes**, evicting oldest-first, per room. Adds `usage(room)
-> int` and `rooms() -> list[str]` to the protocol.

### NullBacklog

Accepts everything, remembers nothing. What `Hub()` uses when given no backlog.

## RoomConsumer

```python
class RoomConsumer:
    hub: ClassVar[Hub | None] = None
    encoding: ClassVar[Encoding] = Encoding.JSON
    capacity: ClassVar[int] = 64
    overflow: ClassVar[Overflow] = Overflow.DROP_OLDEST
```

| Member | |
|---|---|
| `classmethod as_handler(hub=None)` | The coroutine for `add_ws_route` |
| `await identify(ctx)` | Hook → the peer's identity |
| `await rooms(ctx)` | Hook → rooms to join |
| `await on_connect()` | Hook, after joining |
| `await on_message(data)` | Hook, per message |
| `await on_disconnect()` | Hook, always — in a `finally` |
| `await broadcast(payload, room=None)` | Defaults to the first room joined |
| `await reply(payload)` | This connection only |
| `await join(room)` / `await leave(room)` | Mid-connection |
| `self.peer` / `self.ctx` / `self.joined` | Per connection |

## Errors

| | |
|---|---|
| `WireError` | Base for everything the package raises |
| `PeerGone` | The socket is closed and cannot be written to |
| `RoomNotFound` | A room was addressed that has no members |

`broadcast` does not raise `PeerGone` — a dead peer is counted as `failed`,
because one client going away is not a failure of the broadcast.

## Testing

`sillo.wire.testing`. See [Testing](/packages/wire/testing/).

| | |
|---|---|
| `FakeSocket(*, delay=0.0, fail=False)` | `.sent`, `.closed` |
| `await drain(*peers, timeout=1.0)` | Wait for writer tasks to empty |

## Version

```python
from sillo.wire import __version__
```
