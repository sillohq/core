---
title: Testing
description: FakeSocket and drain — testing realtime code without a server, including the slow client and the one that has gone away.
---

A unit test of realtime code is missing exactly one thing: a socket.
`sillo.wire.testing` supplies it.

```python
from sillo.wire import Hub, Peer
from sillo.wire.testing import FakeSocket, drain


async def test_a_broadcast_reaches_the_room():
    hub, socket = Hub(), FakeSocket()
    peer = Peer(socket)
    await hub.join(peer, "lobby")

    await hub.broadcast("lobby", {"hello": True})
    await drain(peer)

    assert socket.sent == [{"hello": True}]
```

No server, no event-loop plumbing, no `asyncio.sleep(0.1)` hoping it was
enough.

## Why `drain` exists

A broadcast **enqueues**. It returns as soon as every peer has accepted the
envelope, which is the whole design — and it means the assertion after it runs
before anything has been written.

`drain(*peers)` waits for the writer tasks to empty those queues:

```python
await drain(peer)                       # one
await drain(*hub.members("lobby"))      # a room
await drain(peer, timeout=5.0)          # slow on purpose
```

Forgetting it produces the worst kind of flake: a test that passes on a fast
machine and fails in CI. If an assertion about `socket.sent` is empty when you
expected it not to be, `drain` is the first thing to check.

## The two clients worth testing

Both are hard to reproduce against a real server, and both are where realtime
code actually breaks.

**The client that reads slowly.**

```python
async def test_a_slow_client_drops_rather_than_blocking_the_room():
    hub = Hub()
    fast, slow = Peer(FakeSocket()), Peer(FakeSocket(delay=0.05), capacity=2)
    await hub.join(fast, "lobby")
    await hub.join(slow, "lobby")

    for index in range(10):
        report = await hub.broadcast("lobby", {"n": index})

    await drain(fast)
    assert len(fast.socket.sent) == 10     # unaffected by the slow peer
    assert report.dropped >= 1             # the slow one fell behind
```

**The client that has gone away.**

```python
async def test_a_dead_socket_is_reported_not_raised():
    hub, peer = Hub(), Peer(FakeSocket(fail=True))
    await hub.join(peer, "lobby")

    report = await hub.broadcast("lobby", {"hello": True})

    assert report.failed == 1
    assert report.delivered == 0
```

`FakeSocket(fail=True)` raises on every write, which is what a socket does once
the other end is gone. The assertion that matters is that nothing propagated:
one dead client must not fail a broadcast for everyone else.

## FakeSocket

```python
FakeSocket(delay=0.0, fail=False)
```

| | |
|---|---|
| `sent` | Everything written, in order |
| `delay` | Seconds each write takes — a slow reader |
| `fail` | Raise on every write — a client that has gone |
| `closed` | Whether `close()` was called |

It answers `send_json`, `send_text`, `send_bytes`, `accept` and `close`, so it
stands in for a socket context wherever one is passed.

## Testing overflow policy

Policy is the thing worth pinning down in a test, because the right answer
differs per application and a change to it is easy to make by accident:

```python
import pytest
from sillo.wire import Overflow


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        (Overflow.DROP_OLDEST, [{"n": 8}, {"n": 9}]),
        (Overflow.DROP_NEWEST, [{"n": 0}, {"n": 1}]),
    ],
)
async def test_which_end_is_kept(policy, expected):
    hub = Hub()
    peer = Peer(FakeSocket(delay=0.01), capacity=2, overflow=policy)
    await hub.join(peer, "lobby")

    for index in range(10):
        await hub.broadcast("lobby", {"n": index})
    await drain(peer)

    assert peer.socket.sent[-2:] == expected
```

## Testing presence and replay

Both are plain assertions once you have a hub:

```python
async def test_presence_counts_people_not_sockets():
    hub = Hub()
    for _ in range(2):                                  # two tabs
        await hub.join(Peer(FakeSocket(), identity="ada"), "lobby")

    assert hub.count("lobby") == 2
    assert hub.identities("lobby") == ["ada"]


async def test_replay_sends_only_what_was_missed():
    hub = Hub(backlog=MemoryBacklog())
    await hub.broadcast("lobby", {"n": 1})
    await hub.broadcast("lobby", {"n": 2})

    latecomer = Peer(FakeSocket())
    await hub.join(latecomer, "lobby")
    sent = await hub.replay(latecomer, "lobby", since=0)
    await drain(latecomer)

    assert sent == 2
    assert latecomer.socket.sent == [{"n": 1}, {"n": 2}]
```

## Testing a consumer

`as_handler()` produces an ordinary route handler, so the framework's
`TestClient` drives it end to end:

```python
def test_chat_broadcasts_to_the_room(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/lobby?user=ada") as ada:
            with client.websocket_connect("/ws/lobby?user=bob") as bob:
                ada.send_json({"text": "hello"})
                assert bob.receive_json() == {"from": "ada", "text": "hello"}
```

Use this for the wiring — routes, path parameters, the handshake — and
`FakeSocket` for everything about behaviour under load, which a real client
cannot be made to do on demand.

## Isolation

A `Hub` is an object with no global registry, so tests need no teardown: build
one per test and let it be collected. If you share one across a module, call
`await hub.close()` in the fixture's teardown so a leftover peer cannot reach
into the next test.
