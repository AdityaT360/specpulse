import json

import pytest

from app.services.openapi_parser import OpenAPISpecError, parse_openapi


def test_parse_json_extracts_operations_and_shared_parameters() -> None:
    document = {
        "openapi": "3.0.3",
        "info": {"title": "Pets", "version": "1.0.0"},
        "paths": {
            "/pets/{pet_id}": {
                "parameters": [
                    {
                        "name": "pet_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "get": {
                    "operationId": "getPet",
                    "summary": "Get one pet",
                    "responses": {"200": {"description": "Found"}},
                },
            }
        },
    }

    parsed = parse_openapi(json.dumps(document).encode(), "pets.json")

    assert parsed.version == "3.0.3"
    assert len(parsed.endpoints) == 1
    assert parsed.endpoints[0].method == "GET"
    assert parsed.endpoints[0].operation_id == "getPet"
    assert parsed.endpoints[0].parameters[0]["name"] == "pet_id"


def test_parse_yaml_extracts_request_body() -> None:
    content = b"""
openapi: 3.1.0
info:
  title: Pet API
  version: 1.0.0
paths:
  /pets:
    post:
      summary: Create a pet
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
      responses:
        '201':
          description: Created
"""

    parsed = parse_openapi(content, "pets.yaml")

    assert parsed.endpoints[0].method == "POST"
    assert parsed.endpoints[0].request_body is not None
    assert parsed.endpoints[0].responses["201"]["description"] == "Created"


def test_parse_yaml_normalizes_date_values_for_json_storage() -> None:
    content = b"""
openapi: 3.0.3
info:
  title: Date API
  version: 1.0.0
paths: {}
x-release-date: 2026-09-21
"""

    parsed = parse_openapi(content, "date-api.yaml")

    assert parsed.document["x-release-date"] == "2026-09-21"


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"swagger": "2.0", "paths": {}}, "supports OpenAPI 3.x"),
        ({"openapi": "3.0.3"}, "paths object"),
    ],
)
def test_parse_rejects_unsupported_documents(document: dict, message: str) -> None:
    with pytest.raises(OpenAPISpecError, match=message):
        parse_openapi(json.dumps(document).encode(), "invalid.json")


def test_parse_rejects_unknown_file_type() -> None:
    with pytest.raises(OpenAPISpecError, match=".json"):
        parse_openapi(b"openapi: 3.0.3", "spec.txt")
