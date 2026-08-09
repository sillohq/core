"""Durability guarantees of the Redis queue.

Every test here is a failure that used to happen. `RedisConnection` took jobs
with `RPOP`, which removes them, and kept no record of who was holding what —
so a worker that died mid-job took the job with it. Separately,
`_migrate_delayed` read the due set and wrote it back in three unguarded
steps, which duplicated jobs under ordinary concurrency and lost one in a
narrow window.

A fake server stands in for Redis so these run everywhere; the code under
test is the real `RedisConnection`, unmodified. `fakeredis` executes the same
Lua the real server does, so the atomicity being asserted is genuinely the
scripts' and not the fake's.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from sillo.work.queue.connection import RedisConnection

fakeredis = pytest.importorskip(
    "fakeredis", reason="fakeredis provides the in-process Redis these tests need"
)
import fakeredis.aioredis


@pytest.fixture
def conn():
    """A RedisConnection talking to an in-process fake server."""
    server = fakeredis.aioredis.FakeRedis(decode_responses=True)

    class _Conn(RedisConnection):
        async def _r(self):
            return server

    c = _Conn(visibility_timeout=30.0)
    c._server = server  # type: ignore[attr-defined]
    return c


def run(coro):
    """Run a coroutine on a fresh loop."""
    return asyncio.run(coro)


class InterleavingClient:
    """A client whose every command yields to the event loop before running.

    Without this the race cannot be reproduced: `fakeredis` resolves each
    command without giving another coroutine a chance to run, so two
    concurrent multi-command sequences execute one after the other and the
    unguarded read-then-write looks correct. Yielding first makes the
    interleaving deterministic rather than a matter of scheduler luck — a
    single `EVAL` still cannot be split, which is the whole point.
    """

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        async def yielding(*args, **kwargs):
            await asyncio.sleep(0)
            return await attr(*args, **kwargs)

        return yielding


async def expire_all_claims(conn, queue="emails"):
    """Wind every outstanding claim deadline into the past.

    Simulates the visibility timeout elapsing without making the test sleep
    for it. A queue with nothing in flight has nothing to expire, which is
    itself a meaningful state — hence the guard rather than an assumption.
    """
    _, _, _, claims = conn._keys(queue)
    held = await conn._server.zrange(claims, 0, -1)
    if held:
        await conn._server.zadd(claims, {member: 0 for member in held})
    return len(held)


# ═════════════════════════════════════════════════════════════════
# A worker that dies must not take the job with it
# ═════════════════════════════════════════════════════════════════


class TestCrashedWorkerKeepsTheJob:
    def test_an_unacknowledged_job_is_still_held(self, conn):
        """Popping no longer destroys the only copy."""

        async def main():
            await conn.push("emails", '{"job":"Welcome"}')
            job_id, _ = await conn.pop("emails")

            # The worker now dies. It never acknowledges.
            assert await conn.in_flight("emails") == 1, "job is held, not lost"
            assert job_id

        run(main())

    def test_the_job_comes_back_after_the_visibility_timeout(self, conn):
        """The recovery path: another worker picks it up."""

        async def main():
            await conn.push("emails", '{"job":"Welcome"}')
            first_id, first_payload = await conn.pop("emails")

            # Worker died. Wind every deadline into the past.
            assert await expire_all_claims(conn) == 1

            second_id, second_payload = await conn.pop("emails")

            assert second_payload == first_payload, "same job, redelivered"
            assert second_id == first_id, "and the same id"

        run(main())

    def test_an_acknowledged_job_is_never_redelivered(self, conn):
        """The other half: ack has to actually release the claim."""

        async def main():
            await conn.push("emails", '{"job":"Welcome"}')
            job_id, _ = await conn.pop("emails")
            await conn.ack("emails", job_id)

            assert await conn.in_flight("emails") == 0

            assert await expire_all_claims(conn) == 0, "the claim is already gone"
            assert await conn.pop("emails") is None, "nothing left to redeliver"

        run(main())

    def test_a_failed_job_is_released_rather_than_redelivered(self, conn):
        """`fail` records elsewhere; the queue just stops holding it."""

        async def main():
            await conn.push("emails", '{"job":"Welcome"}')
            job_id, payload = await conn.pop("emails")
            await conn.fail("emails", job_id, payload, "boom")

            assert await conn.in_flight("emails") == 0

        run(main())

    def test_ack_of_an_unknown_id_is_harmless(self, conn):
        async def main():
            await conn.push("emails", '{"job":"Welcome"}')
            await conn.pop("emails")
            await conn.ack("emails", "not-a-real-job-id")

            assert await conn.in_flight("emails") == 1, "the real claim survives"

        run(main())

    def test_a_job_orphaned_between_move_and_claim_is_adopted(self, conn):
        """The gap `BLMOVE` leaves.

        A crash after the move but before the claim lands puts an entry in
        the in-flight list that no deadline covers. Without the adopt pass it
        would sit there forever, invisible to the sweep.
        """

        async def main():
            key, _, processing, claims = conn._keys("emails")
            await conn._server.lpush(processing, "orphan:{}")  # type: ignore[attr-defined]

            assert await conn._server.zcard(claims) == 0  # type: ignore[attr-defined]

            await conn._reap_expired(await conn._r(), "emails")
            assert await conn._server.zcard(claims) == 1, "adopted"  # type: ignore[attr-defined]

            await conn._server.zadd(claims, {"orphan:{}": 0})  # type: ignore[attr-defined]
            await conn._reap_expired(await conn._r(), "emails")

            assert await conn._server.lrange(key, 0, -1) == ["orphan:{}"]  # type: ignore[attr-defined]

        run(main())


# ═════════════════════════════════════════════════════════════════
# Delayed jobs migrate exactly once
# ═════════════════════════════════════════════════════════════════


class TestDelayedMigration:
    async def _due_job(self, conn, raw="j1:payload"):
        key, delayed, _, _ = conn._keys("emails")
        await conn._server.zadd(delayed, {raw: time.time() - 5})  # type: ignore[attr-defined]
        return key, delayed

    def test_a_due_job_reaches_the_ready_list(self, conn):
        async def main():
            key, _ = await self._due_job(conn)
            await conn._migrate_delayed(await conn._r(), key)

            assert await conn._server.lrange(key, 0, -1) == ["j1:payload"]  # type: ignore[attr-defined]

        run(main())

    def test_concurrent_migrations_do_not_duplicate(self, conn):
        """Used to produce two copies, with no crash involved.

        `pop` migrates on every call, so two workers polling the same queue
        is the ordinary case rather than a rare interleaving.
        """

        async def main():
            key, _ = await self._due_job(conn)
            r = InterleavingClient(await conn._r())

            await asyncio.gather(*(conn._migrate_delayed(r, key) for _ in range(8)))

            assert await conn._server.llen(key) == 1, (  # type: ignore[attr-defined]
                "eight concurrent migrations must not produce eight copies"
            )

        run(main())

    def test_migrating_twice_does_not_duplicate(self, conn):
        """The crash-between-steps case, replayed as a second migration."""

        async def main():
            key, _ = await self._due_job(conn)
            r = await conn._r()

            await conn._migrate_delayed(r, key)
            await conn._migrate_delayed(r, key)

            assert await conn._server.llen(key) == 1  # type: ignore[attr-defined]

        run(main())

    def test_a_job_that_becomes_due_mid_migration_is_not_erased(self, conn):
        """The one genuine loss in the old code.

        It deleted by range — `ZREMRANGEBYSCORE(0, now)` — so anything that
        became due between the read and the delete was removed without ever
        being pushed. Removing by member cannot do that.
        """

        async def main():
            key, delayed = await self._due_job(conn, "old:payload-D")
            r = InterleavingClient(await conn._r())

            async def late_arrival():
                # Lands mid-migration: after the due set has been read, before
                # the old code's range delete would have run.
                await asyncio.sleep(0)
                await conn._server.zadd(delayed, {"new:payload-E": time.time() - 1})  # type: ignore[attr-defined]

            await asyncio.gather(conn._migrate_delayed(r, key), late_arrival())
            await conn._migrate_delayed(await conn._r(), key)

            ready = await conn._server.lrange(key, 0, -1)  # type: ignore[attr-defined]
            assert "new:payload-E" in ready, "the late arrival survived"
            assert "old:payload-D" in ready

        run(main())

    def test_a_job_that_is_not_due_yet_stays_put(self, conn):
        async def main():
            key, delayed = conn._keys("emails")[0], conn._keys("emails")[1]
            await conn._server.zadd(delayed, {"future:payload": time.time() + 3600})  # type: ignore[attr-defined]

            await conn._migrate_delayed(await conn._r(), key)

            assert await conn._server.llen(key) == 0  # type: ignore[attr-defined]
            assert await conn._server.zcard(delayed) == 1  # type: ignore[attr-defined]

        run(main())

    def test_delayed_jobs_count_towards_size(self, conn):
        """`size` used to report only the ready list, hiding delayed work."""

        async def main():
            await conn.push("emails", "now")
            await conn.push("emails", "later", delay=3600)

            assert await conn.size("emails") == 2

        run(main())


# ═════════════════════════════════════════════════════════════════
# Job ids
# ═════════════════════════════════════════════════════════════════


class TestJobIds:
    def test_identical_payloads_get_distinct_ids(self, conn):
        """`hash(payload)` gave two identical payloads the same id."""

        async def main():
            a = await conn.push("emails", '{"job":"Same"}')
            b = await conn.push("emails", '{"job":"Same"}')

            assert a != b

        run(main())

    def test_ids_carry_no_colon(self, conn):
        """The raw entry is `id:payload`, split on the first colon."""

        async def main():
            job_id = await conn.push("emails", '{"job":"X"}')

            assert ":" not in job_id

        run(main())

    def test_the_id_survives_the_round_trip(self, conn):
        async def main():
            pushed = await conn.push("emails", '{"job":"X"}')
            popped, payload = await conn.pop("emails")

            assert popped == pushed
            assert payload == '{"job":"X"}'

        run(main())


# ═════════════════════════════════════════════════════════════════
# Ordering and basic behaviour still hold
# ═════════════════════════════════════════════════════════════════


class TestUnchangedBehaviour:
    def test_fifo_order(self, conn):
        async def main():
            for n in ("first", "second", "third"):
                await conn.push("emails", n)

            got = [(await conn.pop("emails"))[1] for _ in range(3)]

            assert got == ["first", "second", "third"]

        run(main())

    def test_pop_on_an_empty_queue_returns_none(self, conn):
        async def main():
            assert await conn.pop("emails") is None

        run(main())

    def test_clear_removes_every_key(self, conn):
        async def main():
            await conn.push("emails", "ready")
            await conn.push("emails", "later", delay=3600)
            await conn.push("emails", "held")
            await conn.pop("emails")

            await conn.clear("emails")

            assert await conn.size("emails") == 0
            assert await conn.in_flight("emails") == 0

        run(main())

    def test_queues_are_independent(self, conn):
        async def main():
            await conn.push("emails", "e")
            await conn.push("reports", "r")

            assert (await conn.pop("emails"))[1] == "e"
            assert (await conn.pop("reports"))[1] == "r"

        run(main())
