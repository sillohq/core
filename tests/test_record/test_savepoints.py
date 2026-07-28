"""
Transactions and savepoints.

A savepoint undoes only the work inside its block; the enclosing transaction
stays open and still commits. The defect these guard against was
``savepoint()`` calling ``execute_insert`` with one argument, which raised
``TypeError`` on every backend before touching the database.
"""

import inspect

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model
from sillo.record.transactions import transaction

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class Note(Model):
    id = fields.IntField(pk=True)
    text = fields.CharField(max_length=100)

    class Meta:
        table = "savepoint_notes"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record.test_savepoints"]},
    )
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas()
    yield
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass


async def texts():
    return sorted(note.text for note in await Note.all())


async def test_a_savepoint_block_commits_with_the_transaction():
    async with transaction() as tx:
        await Note.create(text="outer")
        async with tx.savepoint():
            await Note.create(text="inner")

    assert await texts() == ["inner", "outer"]


async def test_a_failing_savepoint_leaves_the_transaction_alive():
    async with transaction() as tx:
        await Note.create(text="before")
        with pytest.raises(ValueError):
            async with tx.savepoint():
                await Note.create(text="doomed")
                raise ValueError("boom")
        await Note.create(text="after")

    assert await texts() == ["after", "before"]


async def test_the_exception_still_propagates_out_of_the_block():
    async with transaction() as tx:
        with pytest.raises(RuntimeError, match="boom"):
            async with tx.savepoint():
                raise RuntimeError("boom")


async def test_savepoints_nest():
    async with transaction() as tx:
        await Note.create(text="level-0")
        async with tx.savepoint() as sp:
            await Note.create(text="level-1")
            async with sp.savepoint():
                await Note.create(text="level-2")

    assert await texts() == ["level-0", "level-1", "level-2"]


async def test_an_inner_savepoint_can_fail_without_losing_the_outer_one():
    async with transaction() as tx:
        async with tx.savepoint() as sp:
            await Note.create(text="kept")
            with pytest.raises(ValueError):
                async with sp.savepoint():
                    await Note.create(text="discarded")
                    raise ValueError("boom")

    assert await texts() == ["kept"]


async def test_rolling_back_the_transaction_discards_savepoint_work_too():
    with pytest.raises(RuntimeError):
        async with transaction() as tx:
            await Note.create(text="outer")
            async with tx.savepoint():
                await Note.create(text="inner")
            raise RuntimeError("outer failure")

    assert await texts() == []


async def test_two_sequential_savepoints_do_not_collide():
    """Names are generated per savepoint; a fixed name would clash here."""
    async with transaction() as tx:
        async with tx.savepoint():
            await Note.create(text="first")
        async with tx.savepoint():
            await Note.create(text="second")

    assert await texts() == ["first", "second"]
