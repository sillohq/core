"""``sillo.graphql.handler`` — the request paths around schema execution.

The happy path is covered elsewhere; what was unreached here is everything
that goes wrong or is switched off — GraphiQL disabled, a body that is not
JSON, a body that is JSON but not an object, a query that produces GraphQL
errors, and the guard for a missing strawberry install.
"""

import pytest

from sillo import SilloApp
from sillo.testclient import TestClient

strawberry = pytest.importorskip(
    "strawberry", reason="strawberry-graphql is an optional dependency"
)

from sillo.graphql.handler import GraphQL  # noqa: E402


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "world"

    @strawberry.field
    def boom(self) -> str:
        raise ValueError("resolver exploded")


SCHEMA = strawberry.Schema(query=Query)


def build(**kwargs):
    app = SilloApp(debug=False)
    GraphQL(app, SCHEMA, **kwargs)
    return app


class TestGraphiQL:
    def test_get_serves_the_ide_by_default(self):
        with TestClient(build()) as client:
            response = client.get("/graphql")

        assert response.status_code == 200
        assert "graphiql" in response.text.lower()

    def test_get_is_404_when_the_ide_is_disabled(self):
        with TestClient(build(graphiql=False)) as client:
            response = client.get("/graphql")

        assert response.status_code == 404
        assert response.text == "Not Found"

    def test_the_path_is_configurable(self):
        with TestClient(build(path="/api/graph")) as client:
            assert client.get("/api/graph").status_code == 200


class TestExecution:
    def test_a_query_returns_data(self):
        with TestClient(build()) as client:
            response = client.post("/graphql", json={"query": "{ hello }"})

        assert response.status_code == 200
        assert response.json()["data"] == {"hello": "world"}

    def test_a_failing_resolver_returns_formatted_errors(self):
        with TestClient(build()) as client:
            response = client.post("/graphql", json={"query": "{ boom }"})

        payload = response.json()
        assert "errors" in payload
        assert payload["errors"][0]["message"] == "resolver exploded"

    def test_variables_and_operation_name_are_forwarded(self):
        with TestClient(build()) as client:
            response = client.post(
                "/graphql",
                json={
                    "query": "query Named { hello }",
                    "variables": {},
                    "operationName": "Named",
                },
            )

        assert response.json()["data"] == {"hello": "world"}


class TestMalformedBodies:
    def test_a_non_json_body_is_a_400(self):
        with TestClient(build()) as client:
            response = client.post(
                "/graphql",
                content=b"this is not json",
                headers={"content-type": "application/json"},
            )

        assert response.status_code == 400
        assert response.json()["errors"][0]["message"] == "Invalid JSON body"

    @pytest.mark.parametrize("body", [[1, 2, 3], "a string", 42])
    def test_a_json_body_that_is_not_an_object_is_a_400(self, body):
        with TestClient(build()) as client:
            response = client.post("/graphql", json=body)

        assert response.status_code == 400
        assert response.json()["errors"][0]["message"] == "JSON body must be an object"


class TestMissingDependency:
    def test_construction_reports_how_to_install_strawberry(self, monkeypatch):
        import sillo.graphql.handler as handler

        monkeypatch.setattr(handler, "HAS_STRAWBERRY", False)

        with pytest.raises(ImportError, match="strawberry-graphql"):
            handler.GraphQL(SilloApp(debug=False), SCHEMA)
