"""
The driver contract, as assertions.

One suite, run against every driver.  Not per-driver tests: "works locally,
breaks on S3" is the entire failure mode of a storage layer, and this structure
is the only one that catches it.  A backend that disagrees with anything here
disagrees with the contract, whoever wrote it.

Written before the second driver existed, on purpose.  Write it afterwards and
the contract quietly becomes "whatever the first driver happened to do".

Anybody writing a third-party driver imports :class:`DriverContract`, gives it a
fixture, and finds out whether they are finished.
"""

from __future__ import annotations

import pytest

from sillo.storage.base import chunks, collect
from sillo.storage.errors import FileNotFound


class DriverContract:
    """Everything a :class:`~sillo.storage.base.Driver` must do.

    Subclass it and provide a ``driver`` fixture.
    """

    # -- writing and reading --------------------------------------------

    async def test_what_was_written_comes_back(self, driver):
        await driver.write("a.txt", chunks(b"hello"), content_type="text/plain")
        assert await collect(driver.read("a.txt")) == b"hello"

    async def test_an_empty_object_is_an_object(self, driver):
        """Zero bytes is a file, not an absence."""
        await driver.write("empty.bin", chunks(b""))
        assert await collect(driver.read("empty.bin")) == b""
        assert (await driver.stat("empty.bin")).size == 0

    async def test_a_large_object_survives_chunking(self, driver):
        payload = bytes(range(256)) * 8192
        await driver.write("big.bin", chunks(payload, size=4096))
        assert await collect(driver.read("big.bin")) == payload

    async def test_writing_again_replaces(self, driver):
        await driver.write("a.txt", chunks(b"first"))
        await driver.write("a.txt", chunks(b"second"))
        assert await collect(driver.read("a.txt")) == b"second"

    async def test_the_content_type_is_kept(self, driver):
        await driver.write("a.txt", chunks(b"x"), content_type="text/csv")
        assert (await driver.stat("a.txt")).content_type == "text/csv"

    async def test_the_size_is_reported(self, driver):
        stored = await driver.write("a.txt", chunks(b"12345"))
        assert stored.size == 5
        assert (await driver.stat("a.txt")).size == 5

    async def test_nested_keys_work(self, driver):
        await driver.write("a/b/c/d.txt", chunks(b"deep"))
        assert await collect(driver.read("a/b/c/d.txt")) == b"deep"

    async def test_a_unicode_key_works(self, driver):
        await driver.write("café/résumé.pdf", chunks(b"x"))
        assert await driver.exists("café/résumé.pdf")

    async def test_a_key_with_spaces_works(self, driver):
        await driver.write("my documents/a file.txt", chunks(b"x"))
        assert await driver.exists("my documents/a file.txt")

    # -- absence --------------------------------------------------------

    async def test_reading_something_absent_raises(self, driver):
        with pytest.raises(FileNotFound):
            await collect(driver.read("nope.txt"))

    async def test_stat_of_something_absent_raises(self, driver):
        with pytest.raises(FileNotFound):
            await driver.stat("nope.txt")

    async def test_exists_is_false_rather_than_raising(self, driver):
        assert await driver.exists("nope.txt") is False

    async def test_deleting_something_absent_is_not_an_error(self, driver):
        """The caller wanted it gone. It is gone."""
        assert await driver.delete("nope.txt") is False

    # -- deleting -------------------------------------------------------

    async def test_deleting_removes(self, driver):
        await driver.write("a.txt", chunks(b"x"))
        assert await driver.delete("a.txt") is True
        assert await driver.exists("a.txt") is False

    async def test_deleting_one_leaves_its_neighbours(self, driver):
        await driver.write("a/one.txt", chunks(b"1"))
        await driver.write("a/two.txt", chunks(b"2"))
        await driver.delete("a/one.txt")
        assert await driver.exists("a/two.txt")

    # -- listing --------------------------------------------------------

    async def test_listing_finds_what_was_written(self, driver):
        for index in range(3):
            await driver.write(f"a/{index}.txt", chunks(b"x"))

        page = await driver.page("a/")
        assert {info.key for info in page.files} == {"a/0.txt", "a/1.txt", "a/2.txt"}

    async def test_a_prefix_excludes_everything_else(self, driver):
        await driver.write("wanted/a.txt", chunks(b"x"))
        await driver.write("other/b.txt", chunks(b"x"))

        page = await driver.page("wanted/")
        assert {info.key for info in page.files} == {"wanted/a.txt"}

    async def test_an_empty_prefix_lists_everything(self, driver):
        await driver.write("a.txt", chunks(b"x"))
        await driver.write("b/c.txt", chunks(b"x"))
        assert len((await driver.page()).files) == 2

    async def test_listing_nothing_is_an_empty_page(self, driver):
        page = await driver.page("nothing/")
        assert page.files == () and page.more is False

    async def test_a_page_respects_its_limit(self, driver):
        for index in range(10):
            await driver.write(f"a/{index}.txt", chunks(b"x"))

        assert len((await driver.page("a/", limit=4)).files) == 4

    async def test_the_cursor_reaches_the_rest(self, driver):
        """S3 pages at a thousand keys and local disk does not. A contract that
        returned a plain list would work in development and fall over the first
        time a bucket grew."""
        for index in range(10):
            await driver.write(f"a/{index:02d}.txt", chunks(b"x"))

        seen: list[str] = []
        cursor = ""

        while True:
            page = await driver.page("a/", cursor=cursor, limit=3)
            seen.extend(info.key for info in page.files)
            if not page.more:
                break
            cursor = page.cursor

        assert len(seen) == 10
        assert len(set(seen)) == 10

    async def test_paging_does_not_repeat_a_key(self, driver):
        for index in range(7):
            await driver.write(f"a/{index}.txt", chunks(b"x"))

        first = await driver.page("a/", limit=3)
        second = await driver.page("a/", cursor=first.cursor, limit=3)

        assert not ({i.key for i in first.files} & {i.key for i in second.files})

    async def test_common_prefixes_are_reported(self, driver):
        await driver.write("a/one/x.txt", chunks(b"x"))
        await driver.write("a/two/y.txt", chunks(b"x"))

        assert set((await driver.page("a/")).prefixes) == {"a/one/", "a/two/"}

    # -- copying and moving ---------------------------------------------

    async def test_copying_leaves_the_original(self, driver):
        await driver.write("a.txt", chunks(b"x"), content_type="text/plain")
        await driver.copy("a.txt", "b.txt")

        assert await driver.exists("a.txt")
        assert await collect(driver.read("b.txt")) == b"x"

    async def test_copying_keeps_the_content_type(self, driver):
        await driver.write("a.txt", chunks(b"x"), content_type="text/csv")
        await driver.copy("a.txt", "b.txt")

        assert (await driver.stat("b.txt")).content_type == "text/csv"

    async def test_moving_removes_the_original(self, driver):
        await driver.write("a.txt", chunks(b"x"))
        await driver.move("a.txt", "b.txt")

        assert await driver.exists("a.txt") is False
        assert await driver.exists("b.txt") is True

    # -- watching -------------------------------------------------------

    async def test_a_listener_hears_about_a_write(self, driver):
        heard = []
        driver.listen(heard.append)

        from sillo.storage.base import Action, StorageEvent

        await driver.emit(
            StorageEvent(bucket="b", key="a.txt", action=Action.WRITE, driver=driver.name)
        )
        assert heard and heard[0].key == "a.txt"

    async def test_a_listener_that_raises_cannot_break_anything(self, driver):
        """An observer must not be able to fail a write."""
        from sillo.storage.base import Action, StorageEvent

        def explode(event):
            raise RuntimeError("no")

        driver.listen(explode)
        await driver.emit(
            StorageEvent(bucket="b", key="a", action=Action.READ, driver=driver.name)
        )

    async def test_unlistening_stops_delivery(self, driver):
        from sillo.storage.base import Action, StorageEvent

        heard = []
        driver.listen(heard.append)
        driver.unlisten(heard.append)

        await driver.emit(
            StorageEvent(bucket="b", key="a", action=Action.READ, driver=driver.name)
        )
        assert heard == []

    # -- reporting ------------------------------------------------------

    async def test_it_says_what_it_can_do(self, driver):
        assert (await driver.capabilities())["driver"] == driver.name
