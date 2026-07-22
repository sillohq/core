from pydantic import BaseModel, Field

from sillo import silloApp
from sillo.core.http import Request, Response
from sillo.testclient import TestClient


class UserCreate(BaseModel):
    name: str
    email: str
    age: int = Field(ge=0)


def test_request_model_validated_data_on_request():
    """request_model validates body and sets request.validated_data."""
    app = silloApp()

    @app.post("/users", request_model=UserCreate)
    async def create_user(request: Request, response: Response):
        user = request.validated_data
        assert isinstance(user, UserCreate)
        return response.json(user.model_dump(), status_code=201)

    client = TestClient(app)
    resp = client.post("/users", json={"name": "Alice", "email": "alice@test.com", "age": 30})

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@test.com"
    assert data["age"] == 30


def test_request_model_injected_as_third_param():
    """When handler has third positional param, validated data is injected."""
    app = silloApp()

    @app.post("/users", request_model=UserCreate)
    async def create_user(request: Request, response: Response, data):
        return response.json({"name": data.name, "age": data.age}, status_code=201)

    client = TestClient(app)
    resp = client.post("/users", json={"name": "Bob", "email": "bob@test.com", "age": 25})

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Bob"
    assert data["age"] == 25


def test_request_model_validation_error():
    """Invalid body returns 422 with Pydantic error details."""
    app = silloApp()

    @app.post("/users", request_model=UserCreate)
    async def create_user(request: Request, response: Response):
        return response.json({"ok": True})

    client = TestClient(app)
    resp = client.post("/users", json={"name": "Eve"})

    assert resp.status_code == 422
    errors = resp.json()
    assert isinstance(errors, list)
    assert any(e["loc"] == ["email"] for e in errors)
    assert any(e["loc"] == ["age"] for e in errors)


def test_request_model_with_di_does_not_clash():
    """Handler with Depend and request_model — validated_data goes to request, not injected."""
    from sillo.core.dependencies import Depend

    app = silloApp()

    def get_db():
        return "db_connected"

    @app.post("/users", request_model=UserCreate)
    async def create_user(request: Request, response: Response, db: str = Depend(get_db)):
        user = request.validated_data
        return response.json({"name": user.name, "db": db})

    client = TestClient(app)
    resp = client.post("/users", json={"name": "Carl", "email": "carl@test.com", "age": 40})

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Carl"
    assert data["db"] == "db_connected"


def test_no_request_model_no_validation():
    """Without request_model, validated_data is None."""
    app = silloApp()

    @app.post("/echo")
    async def echo(request: Request, response: Response):
        assert request.validated_data is None
        return response.json({"ok": True})

    client = TestClient(app)
    resp = client.post("/echo", json={"anything": "goes"})
    assert resp.status_code == 200
