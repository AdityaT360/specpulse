import json
from contextlib import nullcontext

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import worker
from app.api.routes import test_runs
from app.core.config import settings
from app.db.models import TestRun as StoredRun
from app.services.test_runner import TargetNotAllowed, execute_test_run, validate_target


@pytest.fixture(autouse=True)
def allow_demo_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "run_target_hosts", "demo-target,localhost")


def _make_cases(client: TestClient, base_url: str = "http://demo-target:8001") -> tuple[int, int]:
    project = client.post("/projects", json={"name": "Pets", "base_url": base_url})
    assert project.status_code == 201
    project_id = project.json()["id"]
    document = {
        "openapi": "3.0.3",
        "paths": {
            "/pets": {
                "get": {"responses": {"200": {}}},
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "responses": {"201": {}},
                },
            }
        },
    }
    upload = client.post(
        f"/projects/{project_id}/specs",
        files={"file": ("pets.json", json.dumps(document), "application/json")},
    )
    assert upload.status_code == 201
    spec_id = upload.json()["id"]
    assert client.post(f"/specs/{spec_id}/test-cases/generate").status_code == 200
    return project_id, spec_id


def _queue_run(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, project_id: int, spec_id: int
) -> int:
    queued: list[int] = []
    monkeypatch.setattr(test_runs.execute_test_run_task, "delay", queued.append)
    response = client.post(
        f"/projects/{project_id}/test-runs",
        json={"spec_id": spec_id, "confirm_mutating_requests": True},
    )
    assert response.status_code == 202
    run_id = response.json()["id"]
    assert queued == [run_id]
    return run_id


def test_run_requires_confirmation_and_queues_work(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, spec_id = _make_cases(client)
    rejected = client.post(f"/projects/{project_id}/test-runs", json={"spec_id": spec_id})
    assert rejected.status_code == 422
    assert "confirm_mutating_requests" in rejected.json()["detail"]

    run_id = _queue_run(client, monkeypatch, project_id, spec_id)
    run = client.get(f"/test-runs/{run_id}").json()
    assert run["status"] == "queued"
    assert run["total_tests"] == 2
    assert run["passed"] == run["failed"] == 0
    assert client.get(f"/projects/{project_id}/test-runs").json()[0]["id"] == run_id
    assert client.get(f"/test-runs/{run_id}/results").json() == []


def test_worker_executes_cases_and_stores_results(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, spec_id = _make_cases(client)
    run_id = _queue_run(client, monkeypatch, project_id, spec_id)
    requests: list[tuple[str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url)))
        if request.method == "POST":
            assert json.loads(request.content) == {"name": "sample"}
            return httpx.Response(201)
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
        execute_test_run(db_session, run_id, http_client)
        execute_test_run(db_session, run_id, http_client)

    assert requests == [
        ("GET", "http://demo-target:8001/pets"),
        ("POST", "http://demo-target:8001/pets"),
    ]
    run = client.get(f"/test-runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["passed"] == 2
    assert run["failed"] == 0
    assert run["started_at"] is not None
    assert run["finished_at"] is not None
    results = client.get(f"/test-runs/{run_id}/results").json()
    assert [item["status"] for item in results] == ["passed", "passed"]
    assert [item["actual_status"] for item in results] == [200, 201]
    assert all(item["latency_ms"] >= 0 for item in results)


def test_http_mismatch_and_connection_error_are_recorded(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, spec_id = _make_cases(client)
    run_id = _queue_run(client, monkeypatch, project_id, spec_id)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            raise httpx.ConnectError("Target unavailable", request=request)
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
        execute_test_run(db_session, run_id, http_client)

    run = client.get(f"/test-runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["failed"] == 2
    results = client.get(f"/test-runs/{run_id}/results").json()
    assert results[0]["actual_status"] == 500
    assert "Expected HTTP 200" in results[0]["error_message"]
    assert results[1]["actual_status"] is None
    assert "Target unavailable" in results[1]["error_message"]


def test_unapproved_target_is_rejected(client: TestClient) -> None:
    project_id, spec_id = _make_cases(client, "https://example.com")
    response = client.post(
        f"/projects/{project_id}/test-runs",
        json={"spec_id": spec_id, "confirm_mutating_requests": True},
    )
    assert response.status_code == 422
    assert client.get(f"/projects/{project_id}/test-runs").json() == []


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "file:///etc/passwd",
        "http://user:pass@demo-target:8001",
        "http://demo-target:8001?next=elsewhere",
        "http://demo-target\\@elsewhere",
    ],
)
def test_target_url_guard_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(TargetNotAllowed):
        validate_target(url)


def test_broker_failure_marks_run_failed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, spec_id = _make_cases(client)

    def fail_to_queue(_run_id: int) -> None:
        raise ConnectionError("Redis is down")

    monkeypatch.setattr(test_runs.execute_test_run_task, "delay", fail_to_queue)
    response = client.post(
        f"/projects/{project_id}/test-runs",
        json={"spec_id": spec_id, "confirm_mutating_requests": True},
    )
    assert response.status_code == 503
    run = db_session.scalars(select(StoredRun)).one()
    assert run.status == "failed"
    assert run.finished_at is not None


def test_run_routes_return_not_found(client: TestClient) -> None:
    assert client.get("/projects/999/test-runs").status_code == 404
    assert client.get("/test-runs/999").status_code == 404
    assert client.get("/test-runs/999/results").status_code == 404


def test_worker_rechecks_target_before_sending_requests(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, spec_id = _make_cases(client)
    run_id = _queue_run(client, monkeypatch, project_id, spec_id)
    monkeypatch.setattr(settings, "run_target_hosts", "localhost")
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
        with pytest.raises(TargetNotAllowed):
            execute_test_run(db_session, run_id, http_client)
    assert requests == []
    assert client.get(f"/test-runs/{run_id}").json()["status"] == "failed"


def test_demo_target_matches_sample_spec() -> None:
    from examples.demo_target import app

    with TestClient(app) as client:
        assert client.get("/pets").status_code == 200
        response = client.post("/pets", json={"name": "sample"})
        assert response.status_code == 201
        assert response.json() == {"name": "sample"}


def test_celery_task_invokes_runner_in_eager_mode(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def record_run(db: Session, run_id: int, _client: httpx.Client) -> None:
        assert db is db_session
        calls.append(run_id)

    monkeypatch.setitem(worker.celery_app.conf, "task_always_eager", True)
    monkeypatch.setitem(worker.celery_app.conf, "task_eager_propagates", True)
    monkeypatch.setattr(worker, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(worker, "execute_test_run", record_run)
    worker.execute_test_run_task.delay(42)
    assert calls == [42]
