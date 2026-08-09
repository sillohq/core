import pytest
from pydantic import BaseModel

from sillo import SilloApp
from sillo.testclient import TestClient


@pytest.fixture
def app():
    return SilloApp()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def strict_app():
    """An app with every parameter opted into Pydantic validation."""
    return SilloApp(strict_validation=True)


class UserCreate(BaseModel):
    name: str
    age: int


class UserOut(BaseModel):
    id: int
    name: str
