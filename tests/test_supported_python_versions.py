"""Keeps the three places that claim a Python version telling the same story.

``requires-python`` decides what pip will install onto, the classifiers are what
PyPI shows a reader, and the CI matrix is the only one of the three backed by a
test run. They drifted once already: there were no classifiers at all, so the
project page listed no supported versions for any release while CI stopped two
versions below what the metadata allowed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 only
    tomllib = pytest.importorskip("tomli")

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
WORKFLOWS = ROOT / ".github" / "workflows"

#: Released versions the project commits to. A version in this tuple must be in
#: the classifiers, in every CI matrix, and at or above ``requires-python``.
SUPPORTED = ("3.10", "3.11", "3.12", "3.13", "3.14")

#: Run in CI so breakage surfaces early, but not claimed on PyPI and not a gate
#: while it is a pre-release. Move it into SUPPORTED when it ships final.
PRERELEASE = ("3.15",)


def _metadata() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]


def _matrix(workflow: str) -> list[str]:
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    match = re.search(r"python-version:\s*\[([^\]]+)\]", text)
    assert match is not None, f"no python-version matrix found in {workflow}"
    return re.findall(r'"([^"]+)"', match.group(1))


MATRIX_WORKFLOWS = ("run-tests.yaml", "type-check.yaml")


class TestRequiresPython:
    def test_floor_matches_the_lowest_supported_version(self):
        assert _metadata()["requires-python"] == f">={SUPPORTED[0]}"

    def test_the_running_interpreter_satisfies_it(self):
        floor = tuple(int(p) for p in SUPPORTED[0].split("."))
        assert sys.version_info[:2] >= floor


class TestClassifiers:
    def test_every_supported_version_is_declared(self):
        classifiers = _metadata()["classifiers"]
        for version in SUPPORTED:
            assert f"Programming Language :: Python :: {version}" in classifiers

    def test_prereleases_are_not_claimed(self):
        classifiers = _metadata()["classifiers"]
        for version in PRERELEASE:
            assert f"Programming Language :: Python :: {version}" not in classifiers

    def test_no_version_is_claimed_that_ci_does_not_run(self):
        declared = {
            c.rsplit(" :: ", 1)[1]
            for c in _metadata()["classifiers"]
            if c.startswith("Programming Language :: Python :: 3.")
        }
        assert declared == set(SUPPORTED)

    def test_license_stays_an_spdx_expression(self):
        # `license` is SPDX under PEP 639, and a `License ::` classifier
        # alongside it is what makes the build back end reject the metadata.
        metadata = _metadata()
        assert isinstance(metadata["license"], str)
        assert not [c for c in metadata["classifiers"] if c.startswith("License ::")]


class TestCIMatrix:
    @pytest.mark.parametrize("workflow", MATRIX_WORKFLOWS)
    def test_runs_every_supported_version(self, workflow: str):
        assert set(_matrix(workflow)) >= set(SUPPORTED)

    @pytest.mark.parametrize("workflow", MATRIX_WORKFLOWS)
    def test_runs_the_prereleases(self, workflow: str):
        assert set(_matrix(workflow)) >= set(PRERELEASE)

    @pytest.mark.parametrize("workflow", MATRIX_WORKFLOWS)
    def test_runs_nothing_beyond_what_is_declared(self, workflow: str):
        assert set(_matrix(workflow)) == set(SUPPORTED) | set(PRERELEASE)

    @pytest.mark.parametrize("workflow", MATRIX_WORKFLOWS)
    def test_a_prerelease_leg_can_resolve_and_cannot_gate(self, workflow: str):
        text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
        # setup-python refuses to resolve a beta without this.
        assert "allow-prereleases: true" in text
        # A beta regressing upstream must not turn the branch red.
        assert "continue-on-error:" in text
        # One version failing should still let the rest report.
        assert "fail-fast: false" in text


class TestNoRemovedStdlibCalls:
    """``asyncio.iscoroutinefunction`` is slated for removal in 3.16."""

    def test_source_uses_the_inspect_spelling(self):
        offenders = [
            path.relative_to(ROOT)
            for path in (ROOT / "sillo").rglob("*.py")
            if "asyncio.iscoroutinefunction" in path.read_text(encoding="utf-8")
        ]
        assert offenders == []
