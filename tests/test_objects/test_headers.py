"""
``Headers``, ``MutableHeaders``, ``QueryParams``, ``UploadedFile``, ``FormData``.

HTTP header names are case-insensitive on the wire, so every lookup, deletion
and containment check has to be too — that is what most of this file is about.
"""

import os

import pytest

import io

from sillo.objects.http import (
    FormData,
    Headers,
    MutableHeaders,
    QueryParams,
    UploadedFile,
)


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def _upload(filename="a.txt", *, headers=None, spool_max_size=1024 * 1024):
    """An ``UploadedFile`` over a spooled temporary file, as the parser builds it."""
    import tempfile

    return UploadedFile(
        tempfile.SpooledTemporaryFile(max_size=spool_max_size),
        size=0,
        filename=filename,
        headers=headers,
    )


# ── QueryParams ──────────────────────────────────────────────────────────


def test_query_params_from_a_string():
    assert QueryParams("a=1&b=2")["a"] == "1"


def test_query_params_from_a_dict():
    assert QueryParams({"a": "1"})["a"] == "1"


def test_query_params_from_pairs():
    assert QueryParams([("a", "1"), ("b", "2")])["b"] == "2"


def test_query_params_from_bytes():
    assert QueryParams(b"a=1")["a"] == "1"


def test_repeated_keys_are_kept():
    params = QueryParams("tag=a&tag=b")
    assert params.getlist("tag") == ["a", "b"]


def test_a_single_lookup_returns_the_last_value():
    """Multi-dict semantics: the subscript answers with the final occurrence,
    and ``getlist`` is how you see them all."""
    assert QueryParams("tag=a&tag=b")["tag"] == "b"


def test_empty_query_params():
    assert len(QueryParams("")) == 0


def test_the_string_form_round_trips():
    assert QueryParams(str(QueryParams("a=1&b=2")))["b"] == "2"


def test_the_repr_names_the_class():
    assert "QueryParams" in repr(QueryParams("a=1"))


def test_calling_query_params_gives_a_dict():
    assert QueryParams("a=1&b=2")() == {"a": "1", "b": "2"}


def test_percent_encoding_is_decoded():
    assert QueryParams("q=hello%20world")["q"] == "hello world"


# ── Headers: construction ────────────────────────────────────────────────


def test_headers_from_a_dict():
    assert Headers({"Content-Type": "text/html"})["content-type"] == "text/html"


def test_headers_from_a_raw_list():
    headers = Headers(raw=[(b"content-type", b"application/json")])
    assert headers["content-type"] == "application/json"


def test_headers_from_a_scope():
    scope = {"headers": [(b"host", b"example.com")]}
    assert Headers(scope=scope)["host"] == "example.com"


def test_empty_headers():
    assert len(Headers()) == 0


def test_the_raw_form_is_bytes():
    raw = Headers({"X-Test": "value"}).raw
    assert all(isinstance(k, bytes) and isinstance(v, bytes) for k, v in raw)


# ── Headers: case-insensitive access ─────────────────────────────────────


@pytest.mark.parametrize("key", ["content-type", "Content-Type", "CONTENT-TYPE"])
def test_lookup_ignores_case(key):
    assert Headers({"content-type": "text/html"})[key] == "text/html"


def test_containment_ignores_case():
    headers = Headers({"Content-Type": "text/html"})
    assert "content-type" in headers
    assert "CONTENT-TYPE" in headers


def test_a_missing_header_is_not_contained():
    assert "x-nope" not in Headers({"a": "1"})


def test_a_missing_header_reads_as_none():
    """Deliberately not a ``KeyError`` — request code reads optional headers
    constantly, and ``if headers["x-foo"]`` is the idiom that follows."""
    assert Headers({"a": "1"})["x-nope"] is None


def test_get_returns_a_default():
    """Regression: ``Mapping.get`` returns the default by catching
    ``KeyError``, which this class never raises — so the default was silently
    dropped and every lookup answered ``None``."""
    assert Headers({"a": "1"}).get("x-nope", "fallback") == "fallback"


def test_get_without_a_default_is_none():
    assert Headers({"a": "1"}).get("x-nope") is None


def test_a_mutable_header_get_also_honours_the_default():
    assert MutableHeaders({"a": "1"}).get("x-nope", "fallback") == "fallback"


def test_get_finds_a_present_header():
    assert Headers({"a": "1"}).get("A") == "1"


def test_keys_are_lowercased():
    assert list(Headers({"Content-Type": "text/html"}).keys()) == ["content-type"]


def test_values_are_returned():
    assert list(Headers({"a": "1"}).values()) == ["1"]


def test_items_pairs_keys_with_values():
    assert list(Headers({"A": "1"}).items()) == [("a", "1")]


def test_iteration_yields_the_keys():
    assert list(iter(Headers({"A": "1", "B": "2"}))) == ["a", "b"]


def test_the_length_counts_the_headers():
    assert len(Headers({"a": "1", "b": "2"})) == 2


def test_a_repeated_header_is_listed():
    headers = Headers(raw=[(b"set-cookie", b"a=1"), (b"set-cookie", b"b=2")])
    assert headers.getlist("set-cookie") == ["a=1", "b=2"]


def test_getlist_of_a_missing_header_is_empty():
    assert Headers({"a": "1"}).getlist("x-nope") == []


def test_headers_with_the_same_content_are_equal():
    assert Headers({"a": "1"}) == Headers({"A": "1"})


def test_headers_with_different_content_differ():
    assert Headers({"a": "1"}) != Headers({"a": "2"})


def test_headers_are_not_equal_to_a_dict():
    assert Headers({"a": "1"}) != {"a": "1"}


def test_the_repr_shows_the_contents():
    assert "a" in repr(Headers({"a": "1"}))


# ── MutableHeaders ───────────────────────────────────────────────────────


def test_a_mutable_copy_is_independent():
    original = Headers({"a": "1"})
    copy = original.mutablecopy()
    copy["a"] = "2"
    assert original["a"] == "1"
    assert copy["a"] == "2"


def test_setting_a_header():
    headers = MutableHeaders()
    headers["X-Test"] = "value"
    assert headers["x-test"] == "value"


def test_setting_replaces_an_existing_value():
    headers = MutableHeaders({"a": "1"})
    headers["A"] = "2"
    assert headers.getlist("a") == ["2"]


def test_deleting_a_header():
    headers = MutableHeaders({"a": "1", "b": "2"})
    del headers["A"]
    assert "a" not in headers
    assert "b" in headers


def test_deleting_a_missing_header_is_a_no_op():
    headers = MutableHeaders({"a": "1"})
    del headers["x-nope"]
    assert len(headers) == 1


def test_setdefault_inserts_when_absent():
    headers = MutableHeaders()
    assert headers.setdefault("X-Test", "value") == "value"
    assert headers["x-test"] == "value"


def test_setdefault_keeps_an_existing_value():
    headers = MutableHeaders({"a": "1"})
    assert headers.setdefault("A", "2") == "1"
    assert headers["a"] == "1"


def test_update_merges_a_mapping():
    headers = MutableHeaders({"a": "1"})
    headers.update({"b": "2"})
    assert headers["b"] == "2"


def test_update_overwrites_existing_keys():
    headers = MutableHeaders({"a": "1"})
    headers.update({"A": "2"})
    assert headers["a"] == "2"


def test_append_keeps_both_values():
    """``Set-Cookie`` legitimately appears more than once."""
    headers = MutableHeaders()
    headers.append("set-cookie", "a=1")
    headers.append("set-cookie", "b=2")
    assert headers.getlist("set-cookie") == ["a=1", "b=2"]


def test_in_place_or_merges():
    headers = MutableHeaders({"a": "1"})
    headers |= {"b": "2"}
    assert headers["b"] == "2"


def test_in_place_or_rejects_a_non_mapping():
    with pytest.raises(TypeError):
        headers = MutableHeaders({"a": "1"})
        headers |= "not-a-mapping"


def test_or_produces_a_new_object():
    original = MutableHeaders({"a": "1"})
    merged = original | {"b": "2"}
    assert "b" in merged
    assert "b" not in original


def test_or_rejects_a_non_mapping():
    with pytest.raises(TypeError):
        MutableHeaders({"a": "1"}) | "not-a-mapping"


def test_adding_a_vary_header():
    headers = MutableHeaders()
    headers.add_vary_header("Accept-Encoding")
    assert headers["vary"] == "Accept-Encoding"


def test_a_second_vary_value_is_appended():
    headers = MutableHeaders({"vary": "Accept"})
    headers.add_vary_header("Accept-Encoding")
    assert headers["vary"] == "Accept, Accept-Encoding"


def test_the_mutable_raw_form_is_bytes():
    headers = MutableHeaders()
    headers["X-Test"] = "value"
    assert headers.raw == [(b"x-test", b"value")]


# ── UploadedFile ─────────────────────────────────────────────────────────


def test_an_uploaded_file_keeps_its_name():
    upload = _upload("report.pdf")
    assert upload.filename == "report.pdf"


def test_the_content_type_comes_from_the_headers():
    upload = _upload(
        "a.json", headers=Headers({"content-type": "application/json"})
    )
    assert upload.content_type == "application/json"


def test_a_file_without_a_content_type():
    assert _upload("a.bin").content_type is None


def test_a_small_upload_stays_in_memory():
    assert _upload("a.txt")._in_memory is True


def test_writing_and_reading_back():
    upload = _upload("a.txt")
    _run(upload.write(b"hello"))
    _run(upload.seek(0))
    assert _run(upload.read()) == b"hello"


def test_writing_updates_the_size():
    upload = _upload("a.txt")
    _run(upload.write(b"hello"))
    assert upload.size == 5


def test_a_bounded_read():
    upload = _upload("a.txt")
    _run(upload.write(b"hello world"))
    _run(upload.seek(0))
    assert _run(upload.read(5)) == b"hello"


def test_seeking_to_an_offset():
    upload = _upload("a.txt")
    _run(upload.write(b"hello world"))
    _run(upload.seek(6))
    assert _run(upload.read()) == b"world"


def test_saving_to_disk(tmp_path):
    upload = _upload("a.txt")
    _run(upload.write(b"file contents"))
    destination = tmp_path / "saved.txt"
    _run(upload.save(destination))
    assert destination.read_bytes() == b"file contents"


def test_saving_accepts_a_string_path(tmp_path):
    upload = _upload("a.txt")
    _run(upload.write(b"data"))
    destination = str(tmp_path / "saved.txt")
    _run(upload.save(destination))
    assert os.path.exists(destination)


def test_saving_rewinds_first(tmp_path):
    """Regression: the stream is at EOF after a write or a read, and saving
    from there wrote a zero-byte file with no error — losing the upload in the
    common "inspect it, then save it" handler."""
    upload = _upload("a.txt")
    _run(upload.write(b"important"))
    _run(upload.seek(0))
    _run(upload.read())
    destination = tmp_path / "saved.txt"
    _run(upload.save(destination))
    assert destination.read_bytes() == b"important"


def test_saving_a_spilled_upload_also_rewinds(tmp_path):
    upload = _upload("big.bin", spool_max_size=16)
    _run(upload.write(b"y" * 64))
    destination = tmp_path / "saved.bin"
    _run(upload.save(destination))
    assert destination.read_bytes() == b"y" * 64


def test_an_upload_can_be_saved_twice(tmp_path):
    upload = _upload("a.txt")
    _run(upload.write(b"contents"))
    _run(upload.save(tmp_path / "first.txt"))
    _run(upload.save(tmp_path / "second.txt"))
    assert (tmp_path / "second.txt").read_bytes() == b"contents"


def test_closing_an_upload():
    upload = _upload("a.txt")
    _run(upload.write(b"data"))
    _run(upload.close())


def test_the_repr_names_the_file():
    assert "a.txt" in repr(_upload("a.txt"))


def test_a_large_upload_spills_to_disk():
    """Past the spool threshold the payload must not be held in memory."""
    upload = _upload("big.bin", spool_max_size=16)
    _run(upload.write(b"x" * 64))
    assert upload._in_memory is False


def test_a_spilled_upload_still_reads_back():
    upload = _upload("big.bin", spool_max_size=16)
    _run(upload.write(b"x" * 64))
    _run(upload.seek(0))
    assert _run(upload.read()) == b"x" * 64


def test_an_upload_documents_itself_as_a_binary_string():
    """OpenAPI renders file fields as ``type: string, format: binary``, which
    is what makes the upload button appear in the docs UI."""
    from pydantic import BaseModel

    class Form(BaseModel):
        attachment: UploadedFile

    schema = Form.model_json_schema()["properties"]["attachment"]
    assert schema["type"] == "string"
    assert schema["format"] == "binary"


def test_an_upload_field_validates_from_raw_bytes():
    """The core schema takes bytes and constructs the upload; live requests
    bypass it and pass the parsed ``UploadedFile`` straight through."""
    from pydantic import BaseModel

    class Form(BaseModel):
        attachment: UploadedFile

    assert isinstance(Form(attachment=b"raw").attachment, UploadedFile)


# ── FormData ─────────────────────────────────────────────────────────────


def test_form_data_holds_text_fields():
    assert FormData([("name", "Ada")])["name"] == "Ada"


def test_form_data_holds_files():
    upload = _upload("a.txt")
    assert FormData([("file", upload)])["file"] is upload


def test_repeated_form_fields_are_kept():
    form = FormData([("tag", "a"), ("tag", "b")])
    assert form.getlist("tag") == ["a", "b"]


def test_form_data_from_a_dict():
    assert FormData({"name": "Ada"})["name"] == "Ada"


def test_an_empty_form():
    assert len(FormData()) == 0


def test_closing_a_form_closes_its_files():
    upload = _upload("a.txt")
    _run(upload.write(b"data"))
    form = FormData([("file", upload), ("name", "Ada")])
    _run(form.close())


def test_get_returns_a_default_for_a_missing_field():
    assert FormData([("a", "1")]).get("nope", "fallback") == "fallback"
