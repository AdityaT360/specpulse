import json

from fastapi.testclient import TestClient

from app.services.openapi_parser import MAX_SPEC_BYTES


def _create_project(client: TestClient) -> int:
    response = client.post(
        "/projects",
        json={"name": "Pet API", "base_url": "https://example.com"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _sample_spec() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Pet API", "version": "1.0.0"},
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "summary": "List pets",
                    "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "Pet list"}},
                },
                "post": {
                    "operationId": "createPet",
                    "summary": "Create a pet",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            }
        },
    }


def test_upload_spec_stores_and_lists_endpoints(client: TestClient) -> None:
    project_id = _create_project(client)
    upload_response = client.post(
        f"/projects/{project_id}/specs",
        files={
            "file": (
                "pet-api.json",
                json.dumps(_sample_spec()),
                "application/json",
            )
        },
    )

    assert upload_response.status_code == 201
    uploaded = upload_response.json()
    assert uploaded["filename"] == "pet-api.json"
    assert uploaded["openapi_version"] == "3.0.3"
    assert uploaded["endpoint_count"] == 2

    specs_response = client.get(f"/projects/{project_id}/specs")
    endpoints_response = client.get(f"/specs/{uploaded['id']}/endpoints")

    assert specs_response.status_code == 200
    assert specs_response.json()[0]["endpoint_count"] == 2
    assert endpoints_response.status_code == 200
    endpoints = endpoints_response.json()
    assert [item["method"] for item in endpoints] == ["GET", "POST"]
    assert endpoints[1]["has_request_body"] is True
    assert endpoints[0]["parameters"][0]["name"] == "limit"


def test_upload_yaml_spec(client: TestClient) -> None:
    project_id = _create_project(client)
    content = b"""
openapi: 3.1.0
info:
  title: Health API
  version: 1.0.0
paths:
  /health:
    get:
      responses:
        '200':
          description: Healthy
"""

    response = client.post(
        f"/projects/{project_id}/specs",
        files={"file": ("health.yaml", content, "application/yaml")},
    )

    assert response.status_code == 201
    assert response.json()["openapi_version"] == "3.1.0"
    assert response.json()["endpoint_count"] == 1


def test_upload_rejects_invalid_spec(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/specs",
        files={"file": ("invalid.json", "{not-json}", "application/json")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "The uploaded file is not valid JSON or YAML."


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/specs",
        files={"file": ("spec.txt", "openapi: 3.0.3", "text/plain")},
    )

    assert response.status_code == 415


def test_upload_rejects_oversized_file(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/specs",
        files={"file": ("large.json", b"x" * (MAX_SPEC_BYTES + 1), "application/json")},
    )

    assert response.status_code == 413


def test_spec_routes_return_not_found(client: TestClient) -> None:
    upload_response = client.post(
        "/projects/999/specs",
        files={"file": ("pet-api.json", json.dumps(_sample_spec()), "application/json")},
    )
    endpoints_response = client.get("/specs/999/endpoints")

    assert upload_response.status_code == 404
    assert endpoints_response.status_code == 404
