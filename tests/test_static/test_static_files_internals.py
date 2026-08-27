"""Coverage for StaticFiles internals the route-serving tests in
test_static_files.py don't reach directly: directory auto-creation, the
not-a-directory guard, and _is_safe_path()'s resolve-failure branch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sillo.static import StaticFiles


def test_missing_directory_is_created(tmp_path):
    target = tmp_path / "does-not-exist-yet"
    assert not target.exists()

    static = StaticFiles(directory=target)

    assert target.is_dir()
    assert static.directories == [target.resolve()]


def test_a_directory_that_is_actually_a_file_is_refused(tmp_path):
    a_file = tmp_path / "not-a-dir"
    a_file.write_text("x")

    with pytest.raises(ValueError, match="is not a directory"):
        StaticFiles(directory=a_file)


def test_is_safe_path_false_on_resolve_failure(tmp_path, monkeypatch):
    static = StaticFiles(directory=tmp_path)

    def raise_runtime_error(self):
        raise RuntimeError("resolve failed")

    monkeypatch.setattr(Path, "resolve", raise_runtime_error)

    assert static._is_safe_path(tmp_path / "a.txt", tmp_path) is False


async def test_handle_skips_a_directory_whose_path_resolution_fails(
    tmp_path, monkeypatch
):
    from sillo import SilloApp
    from sillo.core.routing import Group
    from sillo.testclient import TestClient

    (tmp_path / "a.txt").write_text("hi")
    static = StaticFiles(directory=tmp_path)

    app = SilloApp()
    app.add_route(Group(path="/static", app=static))

    # Built before patching: SilloApp's own startup path also resolves
    # paths (env file discovery), which a blanket patch would break too.
    with TestClient(app) as client:

        def raise_value_error(self):
            raise ValueError("resolve failed")

        monkeypatch.setattr(Path, "resolve", raise_value_error)

        response = client.get("/static/a.txt")

    # The per-directory ValueError is swallowed, falling through to 404
    # rather than propagating out of the request.
    assert response.status_code == 404
