from sillo.normalize.helpers import (
    normalize_path,
    has_trailing_slash,
    add_trailing_slash,
    remove_trailing_slash,
    get_path_segments,
    join_path_segments,
    is_double_slash,
    clean_url_path,
    normalize_url,
    should_skip_path_processing,
)


class TestNormalizeHelpers:
    def test_normalize_path_double_slashes(self):
        assert normalize_path("//a//b//c//") == "/a/b/c/"
        assert normalize_path("/a/b") == "/a/b"
        assert normalize_path("///") == "/"

    def test_has_trailing_slash(self):
        assert has_trailing_slash("/path/")
        assert not has_trailing_slash("/path")
        assert not has_trailing_slash("/")

    def test_add_trailing_slash(self):
        assert add_trailing_slash("/path") == "/path/"
        assert add_trailing_slash("/path/") == "/path/"

    def test_remove_trailing_slash(self):
        assert remove_trailing_slash("/path/") == "/path"
        assert remove_trailing_slash("/path") == "/path"
        assert remove_trailing_slash("/") == "/"

    def test_get_path_segments(self):
        assert get_path_segments("/a/b/c") == ["a", "b", "c"]
        assert get_path_segments("/") == []
        assert get_path_segments("") == []

    def test_join_path_segments(self):
        assert join_path_segments(["a", "b", "c"]) == "/a/b/c"
        assert join_path_segments(["a", "b"], trailing_slash=True) == "/a/b/"
        assert join_path_segments([]) == "/"

    def test_is_double_slash(self):
        assert is_double_slash("//path")
        assert not is_double_slash("/path")

    def test_clean_url_path(self):
        assert clean_url_path("http://example.com//a//b") == "http://example.com/a/b"

    def test_normalize_url_relative(self):
        assert normalize_url("//a//b") == "/a/b"

    def test_should_skip_path_processing(self):
        assert should_skip_path_processing("/file.js")
        assert should_skip_path_processing("/path?query=1")
        assert should_skip_path_processing("/path#fragment")
        assert not should_skip_path_processing("/api/users")
