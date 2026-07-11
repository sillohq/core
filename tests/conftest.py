import functools

import pytest

from sillo.config import set_config
from sillo.testclient import TestClient


@pytest.fixture
def test_client_factory():
    # anyio_backend_name defined by:
    # https://anyio.readthedocs.io/en/stable/testing.html#specifying-the-backends-to-run-on

    return functools.partial(
        TestClient,
    )


@pytest.fixture(autouse=True)
def reset_config():
    yield
    set_config(None)
