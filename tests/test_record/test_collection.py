"""
Collection: the fluent list wrapper returned by record queries.

Pure in-memory operations, so no database is needed. Note that the key-taking
methods (``pluck``, ``sort_by``, ``sum``, ``group_by``, …) read **attributes**,
because a Collection holds record instances — they do not index into dicts.
"""

import json

import pytest

from sillo.record.collection import Collection


class Item:
    """A stand-in for a record instance."""

    def __init__(self, name, price, tag="x"):
        self.name = name
        self.price = price
        self.tag = tag

    def __eq__(self, other):
        return isinstance(other, Item) and self.name == other.name

    def __hash__(self):
        return hash(self.name)


@pytest.fixture
def numbers():
    return Collection([3, 1, 4, 1, 5, 9, 2, 6])


@pytest.fixture
def items():
    return Collection(
        [
            Item("apple", 3, "fruit"),
            Item("banana", 1, "fruit"),
            Item("carrot", 4, "veg"),
        ]
    )


# ── construction and basics ──────────────────────────────────────────────


def test_empty_collection():
    c = Collection()
    assert c.is_empty() is True
    assert c.is_not_empty() is False
    assert c.count() == 0


def test_a_populated_collection(numbers):
    assert numbers.is_empty() is False
    assert numbers.is_not_empty() is True
    assert numbers.count() == 8


def test_len(numbers):
    assert len(numbers) == 8


def test_iteration(numbers):
    assert list(numbers) == [3, 1, 4, 1, 5, 9, 2, 6]


def test_indexing(numbers):
    assert numbers[0] == 3


def test_to_list_returns_a_plain_list(numbers):
    result = numbers.to_list()
    assert isinstance(result, list)
    assert result == [3, 1, 4, 1, 5, 9, 2, 6]


def test_repr_reports_the_size(numbers):
    assert "8" in repr(numbers)


# ── first and last ───────────────────────────────────────────────────────


def test_first(numbers):
    assert numbers.first() == 3


def test_last(numbers):
    assert numbers.last() == 6


def test_first_of_an_empty_collection():
    assert Collection().first() is None


def test_last_of_an_empty_collection():
    assert Collection().last() is None


# ── filtering ────────────────────────────────────────────────────────────


def test_filter(numbers):
    assert numbers.filter(lambda n: n > 3).to_list() == [4, 5, 9, 6]


def test_filter_matching_nothing(numbers):
    assert numbers.filter(lambda n: n > 100).is_empty()


def test_reject_is_the_inverse_of_filter(numbers):
    assert numbers.reject(lambda n: n > 3).to_list() == [3, 1, 1, 2]


def test_contains_takes_a_predicate(numbers):
    """Not a membership test — it takes a callback, like filter."""
    assert numbers.contains(lambda n: n == 9) is True
    assert numbers.contains(lambda n: n == 100) is False


def test_unique(numbers):
    assert sorted(numbers.unique().to_list()) == [1, 2, 3, 4, 5, 6, 9]


def test_unique_on_already_distinct_values():
    assert Collection([1, 2, 3]).unique().count() == 3


# ── transformation ───────────────────────────────────────────────────────


def test_map(numbers):
    assert numbers.map(lambda n: n * 2).to_list() == [6, 2, 8, 2, 10, 18, 4, 12]


def test_map_over_an_empty_collection():
    assert Collection().map(lambda n: n).is_empty()


def test_pluck_reads_an_attribute(items):
    assert items.pluck("name").to_list() == ["apple", "banana", "carrot"]


def test_pluck_a_missing_attribute(items):
    assert items.pluck("nonexistent").count() == 3


# ── ordering and slicing ─────────────────────────────────────────────────


def test_sort_by(items):
    assert items.sort_by("price").pluck("name").to_list() == [
        "banana",
        "apple",
        "carrot",
    ]


def test_sort_by_descending(items):
    assert items.sort_by("price", descending=True).pluck("name").first() == "carrot"


def test_take(numbers):
    assert numbers.take(3).to_list() == [3, 1, 4]


def test_take_more_than_exists(numbers):
    assert numbers.take(100).count() == 8


def test_skip(numbers):
    assert numbers.skip(6).to_list() == [2, 6]


def test_skip_everything(numbers):
    assert numbers.skip(100).is_empty()


def test_chunk_yields_collections(numbers):
    """chunk returns an iterator, so it must be consumed."""
    chunks = list(numbers.chunk(3))
    assert len(chunks) == 3
    assert chunks[0].to_list() == [3, 1, 4]
    assert chunks[-1].to_list() == [2, 6]


def test_chunk_of_an_empty_collection():
    assert list(Collection().chunk(3)) == []


# ── aggregation ──────────────────────────────────────────────────────────


def test_sum(numbers):
    assert numbers.sum() == 31


def test_sum_by_attribute(items):
    assert items.sum("price") == 8


def test_sum_of_an_empty_collection():
    assert Collection().sum() == 0


def test_avg(numbers):
    assert numbers.avg() == pytest.approx(31 / 8)


def test_avg_by_attribute(items):
    assert items.avg("price") == pytest.approx(8 / 3)


def test_avg_of_an_empty_collection():
    assert Collection().avg() == 0


def test_min_and_max(numbers):
    assert numbers.min() == 1
    assert numbers.max() == 9


def test_min_and_max_by_attribute(items):
    assert items.min("price") == 1
    assert items.max("price") == 4


def test_min_of_an_empty_collection_raises():
    """Surfaces the underlying ValueError rather than returning None."""
    with pytest.raises(ValueError):
        Collection().min()


# ── grouping ─────────────────────────────────────────────────────────────


def test_group_by(items):
    grouped = items.group_by("tag")
    assert set(grouped.keys()) == {"fruit", "veg"}
    assert grouped["fruit"].count() == 2


def test_group_by_yields_collections(items):
    assert isinstance(items.group_by("tag")["veg"], Collection)


def test_key_by(items):
    keyed = items.key_by("name")
    assert set(keyed.keys()) == {"apple", "banana", "carrot"}


def test_key_by_keeps_the_last_on_collision():
    c = Collection([Item("same", 1), Item("same", 2)])
    assert c.key_by("name")["same"].price == 2


# ── serialization ────────────────────────────────────────────────────────


def test_to_dict_returns_a_list():
    c = Collection([{"a": 1}])
    assert isinstance(c.to_dict(), list)


def test_to_json_is_valid_json():
    c = Collection([{"a": 1}, {"a": 2}])
    assert json.loads(c.to_json()) is not None


def test_to_json_of_an_empty_collection():
    assert json.loads(Collection().to_json()) == []


# ── chaining ─────────────────────────────────────────────────────────────


def test_operations_chain(items):
    result = (
        items.filter(lambda i: i.price > 1).sort_by("price").pluck("name").to_list()
    )
    assert result == ["apple", "carrot"]


def test_chaining_does_not_mutate_the_receiver(numbers):
    numbers.filter(lambda n: n > 3)
    assert numbers.count() == 8
