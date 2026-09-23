import json

from fastapi.testclient import TestClient


def _upload(client: TestClient, document: dict) -> int:
    project = client.post("/projects", json={"name": "Example API"})
    assert project.status_code == 201
    response = client.post(
        f"/projects/{project.json()['id']}/specs",
        files={"file": ("example.json", json.dumps(document), "application/json")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_generate_and_list_cases_for_get_and_post(client: TestClient) -> None:
    spec_id = _upload(
        client,
        {
            "openapi": "3.0.3",
            "paths": {
                "/pets/{id}": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "get": {
                        "parameters": [
                            {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                            {
                                "name": "X-Region",
                                "in": "header",
                                "required": True,
                                "schema": {"type": "string", "example": "us"},
                            },
                        ],
                        "responses": {"404": {}, "200": {}},
                    },
                    "post": {
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"}
                                }
                            },
                        },
                        "responses": {"201": {}},
                    },
                }
            },
            "components": {
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "required": ["name", "active"],
                        "properties": {
                            "name": {"type": "string"},
                            "active": {"type": "boolean"},
                        },
                    }
                }
            },
        },
    )
    assert client.get(f"/specs/{spec_id}/test-cases").json() == []
    generated = client.post(f"/specs/{spec_id}/test-cases/generate")
    assert generated.status_code == 200
    get_case, post_case = generated.json()
    assert get_case["expected_status"] == 200
    assert get_case["path_params"] == {"id": 1}
    assert get_case["query_params"] == {}
    assert get_case["headers"] == {"X-Region": "us"}
    assert get_case["request_payload"] is None
    assert post_case["expected_status"] == 201
    assert post_case["request_payload"] == {"name": "sample", "active": True}
    assert post_case["headers"] == {"Content-Type": "application/json"}
    assert client.get(f"/specs/{spec_id}/test-cases").json() == generated.json()


def test_generation_is_repeatable_without_duplicates(client: TestClient) -> None:
    spec_id = _upload(
        client,
        {"openapi": "3.0.3", "paths": {"/health": {"get": {"responses": {"204": {}}}}}},
    )
    first = client.post(f"/specs/{spec_id}/test-cases/generate")
    second = client.post(f"/specs/{spec_id}/test-cases/generate")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()[0]["expected_status"] == 204


def test_unsupported_schema_does_not_store_partial_cases(client: TestClient) -> None:
    spec_id = _upload(
        client,
        {
            "openapi": "3.0.3",
            "paths": {
                "/a": {"get": {"responses": {"200": {}}}},
                "/z": {
                    "post": {
                        "requestBody": {
                            "required": True,
                            "content": {"application/json": {"schema": {"allOf": []}}},
                        },
                        "responses": {"201": {}},
                    }
                },
            },
        },
    )
    response = client.post(f"/specs/{spec_id}/test-cases/generate")
    assert response.status_code == 422
    assert "Unsupported schema type" in response.json()["detail"]
    assert client.get(f"/specs/{spec_id}/test-cases").json() == []


def test_missing_reference_is_reported(client: TestClient) -> None:
    spec_id = _upload(
        client,
        {
            "openapi": "3.0.3",
            "paths": {
                "/pets": {
                    "post": {
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Missing"}
                                }
                            },
                        },
                        "responses": {"201": {}},
                    }
                }
            },
        },
    )
    response = client.post(f"/specs/{spec_id}/test-cases/generate")
    assert response.status_code == 422
    assert "Unresolved reference" in response.json()["detail"]


def test_missing_spec_returns_404(client: TestClient) -> None:
    assert client.post("/specs/999/test-cases/generate").status_code == 404
    assert client.get("/specs/999/test-cases").status_code == 404


def test_missing_path_parameter_cannot_produce_a_draft(client: TestClient) -> None:
    spec_id = _upload(
        client,
        {"openapi": "3.0.3", "paths": {"/pets/{id}": {"get": {"responses": {"200": {}}}}}},
    )
    response = client.post(f"/specs/{spec_id}/test-cases/generate")
    assert response.status_code == 422
    assert "Missing path parameter schemas" in response.json()["detail"]
