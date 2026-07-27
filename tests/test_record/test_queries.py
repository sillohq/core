"""
Query helpers: pagination, streaming iteration, explain plans, and grouping.

These run against a real in-memory SQLite database rather than a stubbed
queryset, so the offset/limit arithmetic is checked against what the database
actually returns.
"""

import inspect

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model
from sillo.record.queries import (
    PaginatedResult,
    count_by,
    explain,
    find_by_ids,
    iter_all,
    paginate,
)

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class QueryWidget(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    category = fields.CharField(max_length=50, default="general")

    class Meta:
        table = "query_widgets"

    def __str__(self):
        return self.name


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record.test_queries"]},
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


async def _seed(count=25, category="general"):
    for i in range(count):
        await QueryWidget.create(name=f"widget-{i:03d}", category=category)


# ── PaginatedResult arithmetic ───────────────────────────────────────────


def test_a_partial_last_page_is_counted():
    assert PaginatedResult([], total=21, page=1, page_size=10).pages == 3


def test_an_exact_multiple_has_no_extra_page():
    assert PaginatedResult([], total=20, page=1, page_size=10).pages == 2


def test_an_empty_result_still_reports_one_page():
    """Zero pages would make "page 1 of 0" appear in the UI."""
    assert PaginatedResult([], total=0, page=1, page_size=10).pages == 1


def test_the_first_page_has_a_next_but_no_previous():
    page = PaginatedResult([], total=30, page=1, page_size=10)
    assert page.has_next is True
    assert page.has_prev is False


def test_a_middle_page_has_both():
    page = PaginatedResult([], total=30, page=2, page_size=10)
    assert page.has_next is True
    assert page.has_prev is True


def test_the_last_page_has_a_previous_but_no_next():
    page = PaginatedResult([], total=30, page=3, page_size=10)
    assert page.has_next is False
    assert page.has_prev is True


def test_a_single_page_has_neither():
    page = PaginatedResult([], total=5, page=1, page_size=10)
    assert page.has_next is False
    assert page.has_prev is False


async def test_to_dict_carries_the_metadata():
    await _seed(5)
    page = await paginate(QueryWidget.all(), page=1, page_size=2)
    dumped = page.to_dict()
    assert dumped["total"] == 5
    assert dumped["page"] == 1
    assert dumped["page_size"] == 2
    assert dumped["pages"] == 3


async def test_to_dict_serialises_the_items():
    await _seed(2)
    dumped = (await paginate(QueryWidget.all())).to_dict()
    assert isinstance(dumped["items"][0], (dict, str))


def test_to_dict_falls_back_to_str_for_plain_objects():
    page = PaginatedResult(["not-a-model"], total=1, page=1, page_size=10)
    assert page.to_dict()["items"] == ["not-a-model"]


# ── paginate ─────────────────────────────────────────────────────────────


async def test_the_first_page_is_the_requested_size():
    await _seed(25)
    page = await paginate(QueryWidget.all(), page=1, page_size=10)
    assert len(page.items) == 10


async def test_the_total_counts_every_row_not_just_the_page():
    await _seed(25)
    assert (await paginate(QueryWidget.all(), page=1, page_size=10)).total == 25


async def test_a_later_page_skips_the_earlier_rows():
    await _seed(25)
    page = await paginate(QueryWidget.all(), page=2, page_size=10)
    assert page.items[0].name == "widget-010"


async def test_a_short_final_page():
    await _seed(25)
    assert len(( await paginate(QueryWidget.all(), page=3, page_size=10)).items) == 5


async def test_a_page_past_the_end_is_empty():
    await _seed(5)
    assert (await paginate(QueryWidget.all(), page=99, page_size=10)).items == []


async def test_pagination_applies_the_ordering():
    await _seed(5)
    page = await paginate(QueryWidget.all(), page=1, page_size=2, ordering="-name")
    assert page.items[0].name == "widget-004"


async def test_pagination_respects_an_existing_filter():
    await _seed(5, category="a")
    await _seed(3, category="b")
    page = await paginate(QueryWidget.filter(category="b"))
    assert page.total == 3


async def test_paginating_an_empty_table():
    page = await paginate(QueryWidget.all())
    assert page.total == 0
    assert page.items == []


# ── iter_all ─────────────────────────────────────────────────────────────


async def test_streaming_yields_every_row():
    await _seed(25)
    seen = [w.name async for w in iter_all(QueryWidget.all(), batch_size=10)]
    assert len(seen) == 25


async def test_streaming_yields_rows_in_order():
    await _seed(6)
    seen = [w.name async for w in iter_all(QueryWidget.all(), batch_size=2)]
    assert seen == sorted(seen)


async def test_streaming_an_empty_table_yields_nothing():
    assert [w async for w in iter_all(QueryWidget.all())] == []


async def test_a_batch_larger_than_the_table_still_works():
    await _seed(3)
    seen = [w async for w in iter_all(QueryWidget.all(), batch_size=1000)]
    assert len(seen) == 3


async def test_a_batch_size_of_one():
    await _seed(4)
    seen = [w async for w in iter_all(QueryWidget.all(), batch_size=1)]
    assert len(seen) == 4


async def test_streaming_respects_a_filter():
    await _seed(4, category="a")
    await _seed(2, category="b")
    seen = [w async for w in iter_all(QueryWidget.filter(category="b"), batch_size=1)]
    assert len(seen) == 2


# ── find_by_ids ──────────────────────────────────────────────────────────


async def test_rows_are_fetched_by_primary_key():
    await _seed(5)
    all_widgets = await QueryWidget.all()
    wanted = [all_widgets[0].id, all_widgets[2].id]
    found = await find_by_ids(QueryWidget.all(), wanted)
    assert {w.id for w in found} == set(wanted)


async def test_unknown_ids_are_simply_absent():
    await _seed(2)
    found = await find_by_ids(QueryWidget.all(), [999, 1000])
    assert found == []


async def test_an_empty_id_list_returns_nothing():
    await _seed(2)
    assert await find_by_ids(QueryWidget.all(), []) == []


async def test_a_mix_of_known_and_unknown_ids():
    await _seed(2)
    existing = (await QueryWidget.all())[0].id
    found = await find_by_ids(QueryWidget.all(), [existing, 9999])
    assert len(found) == 1


# ── count_by ─────────────────────────────────────────────────────────────


async def test_grouping_counts_each_value():
    await _seed(3, category="a")
    await _seed(2, category="b")
    assert await count_by(QueryWidget.all(), "category") == {"a": 3, "b": 2}


async def test_grouping_an_empty_table():
    assert await count_by(QueryWidget.all(), "category") == {}


async def test_grouping_by_a_unique_field_gives_one_each():
    await _seed(3)
    counts = await count_by(QueryWidget.all(), "name")
    assert set(counts.values()) == {1}


async def test_grouping_by_an_unknown_field_buckets_everything_under_none():
    await _seed(2)
    assert await count_by(QueryWidget.all(), "not_a_field") == {"None": 2}


# ── explain ──────────────────────────────────────────────────────────────


async def test_an_explain_plan_is_returned():
    await _seed(2)
    plan = await explain(QueryWidget.all())
    assert isinstance(plan, str)
    assert plan


async def test_explain_reports_failure_rather_than_raising():
    """A backend without EXPLAIN must not take the request down with it."""

    class NotAQueryset:
        def sql(self):
            raise RuntimeError("no sql for you")

    assert "unavailable" in await explain(NotAQueryset())
