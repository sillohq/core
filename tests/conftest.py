import functools

import pytest

from sillo.testclient import TestClient


@pytest.fixture
def test_client_factory():
    return functools.partial(
        TestClient,
    )
