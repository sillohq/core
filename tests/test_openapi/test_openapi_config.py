"""
``OpenAPIConfig``: assembling the reusable ``components`` section of a spec.

Every ``add_*`` method lazily creates both ``components`` and its own
sub-mapping, so each is exercised from a fresh config to cover that
first-write path as well as the append path.
"""

import pytest
from pydantic import BaseModel

from sillo.openapi.config import OpenAPIConfig
from sillo.openapi.models import (
    APIKey,
    Contact,
    Example,
    ExternalDocumentation,
    HTTPBearer,
    License,
    Query,
    Schema,
    Server,
    Tag,
)
from sillo.openapi.models import Response as OpenAPIResponse


class Item(BaseModel):
    name: str
    price: float


@pytest.fixture
def config():
    return OpenAPIConfig(title="Test API", version="2.1.0", description="A test spec")


# ── document metadata ────────────────────────────────────────────────────


def test_the_info_block_carries_the_title_and_version(config):
    assert config.openapi_spec.info.title == "Test API"
    assert config.openapi_spec.info.version == "2.1.0"


def test_the_description_is_recorded(config):
    assert config.openapi_spec.info.description == "A test spec"


def test_the_openapi_version_defaults_to_three():
    assert OpenAPIConfig().openapi_spec.openapi.startswith("3.")


def test_the_openapi_version_can_be_pinned():
    assert OpenAPIConfig(openapi_version="3.1.0").openapi_spec.openapi == "3.1.0"


def test_contact_details_are_recorded():
    contact = Contact(name="Support", email="support@example.com")
    assert OpenAPIConfig(contact=contact).openapi_spec.info.contact.email == (
        "support@example.com"
    )


def test_the_license_is_recorded():
    spec = OpenAPIConfig(license=License(name="BSD-3-Clause")).openapi_spec
    assert spec.info.license.name == "BSD-3-Clause"


def test_terms_of_service_are_recorded():
    spec = OpenAPIConfig(termsOfService="https://example.com/tos").openapi_spec
    assert spec.info.termsOfService == "https://example.com/tos"


def test_a_new_config_starts_with_no_paths(config):
    assert config.openapi_spec.paths == {}


# ── security schemes ─────────────────────────────────────────────────────


def test_a_security_scheme_is_registered(config):
    scheme = HTTPBearer(type="http", scheme="bearer")
    config.add_security_scheme("bearerAuth", scheme)
    assert config.openapi_spec.components.securitySchemes["bearerAuth"] is scheme


def test_several_security_schemes_coexist(config):
    config.add_security_scheme("bearerAuth", HTTPBearer(type="http", scheme="bearer"))
    config.add_security_scheme(
        "apiKey", APIKey(type="apiKey", name="X-API-Key", **{"in": "header"})
    )
    assert set(config.openapi_spec.components.securitySchemes) == {
        "bearerAuth",
        "apiKey",
    }


def test_global_security_can_be_set(config):
    config.set_global_security([{"bearerAuth": []}])
    assert config.openapi_spec.security == [{"bearerAuth": []}]


# ── schemas ──────────────────────────────────────────────────────────────


def test_a_pydantic_model_is_converted_to_a_schema(config):
    config.add_schema("Item", Item)
    schema = config.openapi_spec.components.schemas["Item"]
    assert "name" in schema.properties


def test_a_converted_model_keeps_its_required_fields(config):
    config.add_schema("Item", Item)
    assert set(config.openapi_spec.components.schemas["Item"].required) == {
        "name",
        "price",
    }


def test_a_raw_schema_object_is_stored_as_given(config):
    schema = Schema(type="string", maxLength=10)
    config.add_schema("ShortString", schema)
    assert config.openapi_spec.components.schemas["ShortString"] is schema


def test_schemas_accumulate(config):
    config.add_schema("Item", Item)
    config.add_schema("Other", Schema(type="integer"))
    assert set(config.openapi_spec.components.schemas) == {"Item", "Other"}


def test_a_later_schema_replaces_an_earlier_one_of_the_same_name(config):
    config.add_schema("Thing", Schema(type="string"))
    config.add_schema("Thing", Schema(type="integer"))
    assert config.openapi_spec.components.schemas["Thing"].type == "integer"


# ── parameters, responses and examples ───────────────────────────────────


def test_a_reusable_parameter_is_registered(config):
    param = Query(name="page")
    config.add_parameter("PageParam", param)
    assert config.openapi_spec.components.parameters["PageParam"] is param


def test_a_reusable_response_is_registered(config):
    response = OpenAPIResponse(description="Not found")
    config.add_response("NotFound", response)
    assert config.openapi_spec.components.responses["NotFound"] is response


def test_an_example_is_registered(config):
    example = Example(summary="A sample item", value={"name": "Widget", "price": 9.99})
    config.add_example("ItemExample", example)
    assert config.openapi_spec.components.examples["ItemExample"] is example


def test_examples_accumulate(config):
    config.add_example("First", Example(value=1))
    config.add_example("Second", Example(value=2))
    assert set(config.openapi_spec.components.examples) == {"First", "Second"}


# ── tags ─────────────────────────────────────────────────────────────────


def test_a_tag_is_added(config):
    config.add_tag(Tag(name="users", description="User operations"))
    assert [t.name for t in config.openapi_spec.tags] == ["users"]


def test_tags_accumulate(config):
    config.add_tag(Tag(name="users"))
    config.add_tag(Tag(name="orders"))
    assert [t.name for t in config.openapi_spec.tags] == ["users", "orders"]


def test_a_duplicate_tag_is_ignored(config):
    """Two routers both declaring ``tags=["users"]`` must not double it up in
    the rendered sidebar."""
    config.add_tag(Tag(name="users", description="first"))
    config.add_tag(Tag(name="users", description="second"))
    assert len(config.openapi_spec.tags) == 1
    assert config.openapi_spec.tags[0].description == "first"


# ── servers and external docs ────────────────────────────────────────────


def test_a_server_is_added(config):
    config.add_server(Server(url="https://api.example.com"))
    assert config.openapi_spec.servers[-1].url == "https://api.example.com"


def test_servers_accumulate(config):
    config.add_server(Server(url="https://a.example.com"))
    config.add_server(Server(url="https://b.example.com"))
    urls = [s.url for s in config.openapi_spec.servers]
    assert "https://a.example.com" in urls
    assert "https://b.example.com" in urls


def test_servers_given_at_construction_are_kept():
    config = OpenAPIConfig(servers=[Server(url="https://preset.example.com")])
    assert config.openapi_spec.servers[0].url == "https://preset.example.com"


def test_external_docs_can_be_set(config):
    config.set_external_docs(ExternalDocumentation(url="https://docs.example.com"))
    assert "docs.example.com" in str(config.openapi_spec.externalDocs.url)


# ── reference helpers ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,section",
    [
        ("get_schema_ref", "schemas"),
        ("get_parameter_ref", "parameters"),
        ("get_response_ref", "responses"),
        ("get_example_ref", "examples"),
    ],
)
def test_reference_helpers_point_at_the_right_section(config, method, section):
    assert getattr(config, method)("Thing") == f"#/components/{section}/Thing"


def test_a_reference_resolves_against_what_was_registered(config):
    config.add_schema("Item", Item)
    ref = config.get_schema_ref("Item")
    assert ref.rsplit("/", 1)[-1] in config.openapi_spec.components.schemas


def test_the_spec_serialises(config):
    config.add_schema("Item", Item)
    config.add_tag(Tag(name="items"))
    dumped = config.openapi_spec.model_dump(exclude_none=True)
    assert dumped["info"]["title"] == "Test API"
    assert "Item" in dumped["components"]["schemas"]
