from fastapi.testclient import TestClient


def test_create_and_list_projects(client: TestClient) -> None:
    payload = {
        "name": "Demo API",
        "description": "Sample project for M1.",
        "base_url": "https://example.com",
    }

    create_response = client.post("/projects", json=payload)
    list_response = client.get("/projects")

    assert create_response.status_code == 201
    assert create_response.json()["name"] == "Demo API"
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["base_url"] == "https://example.com/"


def test_duplicate_project_name_returns_conflict(client: TestClient) -> None:
    payload = {"name": "Demo API"}

    first_response = client.post("/projects", json=payload)
    second_response = client.post("/projects", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
