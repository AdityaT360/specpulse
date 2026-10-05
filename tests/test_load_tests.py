import json
import subprocess
from contextlib import nullcontext
from io import StringIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import worker
from app.api.routes import load_tests
from app.core.config import settings
from app.db.models import LoadTest as StoredLoadTest
from app.services import load_runner


@pytest.fixture(autouse=True)
def allow_demo_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "run_target_hosts", "demo-target,localhost")


def _make_cases(client: TestClient, base_url: str = "http://demo-target:8001") -> tuple[int, dict]:
    project = client.post("/projects", json={"name": "Load demo", "base_url": base_url})
    assert project.status_code == 201
    project_id = project.json()["id"]
    document = {
        "openapi": "3.0.3",
        "paths": {
            "/pets": {
                "get": {"responses": {"200": {}}},
                "post": {"responses": {"201": {}}},
            }
        },
    }
    upload = client.post(
        f"/projects/{project_id}/specs",
        files={"file": ("pets.json", json.dumps(document), "application/json")},
    )
    assert upload.status_code == 201
    spec_id = upload.json()["id"]
    cases = client.post(f"/specs/{spec_id}/test-cases/generate").json()
    endpoints = client.get(f"/specs/{spec_id}/endpoints").json()
    methods = {endpoint["id"]: endpoint["method"] for endpoint in endpoints}
    return project_id, {methods[case["endpoint_id"]]: case["id"] for case in cases}


def _queue_load_test(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, project_id: int, case_id: int
) -> int:
    queued: list[int] = []
    monkeypatch.setattr(load_tests.execute_load_test_task, "delay", queued.append)
    response = client.post(
        f"/projects/{project_id}/load-tests",
        json={"test_case_id": case_id, "users": 2, "duration_seconds": 5},
    )
    assert response.status_code == 202
    load_test_id = response.json()["id"]
    assert queued == [load_test_id]
    return load_test_id


def test_api_queues_bounded_get_case(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project_id, cases = _make_cases(client)
    load_test_id = _queue_load_test(client, monkeypatch, project_id, cases["GET"])
    response = client.get(f"/load-tests/{load_test_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["total_requests"] is None
    assert client.get(f"/projects/{project_id}/load-tests").json()[0]["id"] == load_test_id
    second = client.post(
        f"/projects/{project_id}/load-tests", json={"test_case_id": cases["GET"]}
    )
    assert second.status_code == 409


def test_api_rejects_unsafe_input(client: TestClient) -> None:
    project_id, cases = _make_cases(client)
    url = f"/projects/{project_id}/load-tests"
    assert client.post(url, json={"test_case_id": cases["POST"]}).status_code == 422
    assert client.post(url, json={"test_case_id": cases["GET"], "users": 6}).status_code == 422
    assert (
        client.post(url, json={"test_case_id": cases["GET"], "duration_seconds": 31}).status_code
        == 422
    )
    assert client.post(url, json={"test_case_id": 999}).status_code == 404
    missing_project = client.post(
        "/projects/999/load-tests", json={"test_case_id": cases["GET"]}
    )
    assert missing_project.status_code == 404


def test_api_rejects_remote_target(client: TestClient) -> None:
    project_id, cases = _make_cases(client, "https://example.com")
    response = client.post(
        f"/projects/{project_id}/load-tests", json={"test_case_id": cases["GET"]}
    )
    assert response.status_code == 422
    assert client.get(f"/projects/{project_id}/load-tests").json() == []


def test_worker_stores_locust_summary(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, cases = _make_cases(client)
    load_test_id = _queue_load_test(client, monkeypatch, project_id, cases["GET"])
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs["timeout"] == 25
        assert kwargs["env"]["SPECPULSE_LOAD_URL"] == "http://demo-target:8001/pets"
        assert command[command.index("--json-file") + 1].endswith("run")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(load_runner.subprocess, "run", fake_run)
    monkeypatch.setattr(load_runner, "TemporaryDirectory", lambda **_kwargs: nullcontext("/tmp"))
    monkeypatch.setattr(
        load_runner,
        "read_locust_summary",
        lambda path, endpoint_name, duration_seconds: {
            "total_requests": 20,
            "failures": 2,
            "failure_percentage": 10.0,
            "average_latency_ms": 11.5,
            "p95_latency_ms": 24.0,
            "requests_per_second": 4.0,
        },
    )
    load_runner.run_load_test(db_session, load_test_id)
    load_runner.run_load_test(db_session, load_test_id)

    assert len(calls) == 1
    assert calls[0][calls[0].index("--exit-code-on-error") + 1] == "0"
    summary = client.get(f"/load-tests/{load_test_id}").json()
    assert summary["status"] == "completed"
    assert summary["total_requests"] == 20
    assert summary["failures"] == 2
    assert summary["failure_percentage"] == 10.0
    assert summary["average_latency_ms"] == 11.5
    assert summary["p95_latency_ms"] == 24.0
    assert summary["requests_per_second"] == 4.0


def test_worker_rechecks_allowed_target(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, cases = _make_cases(client)
    load_test_id = _queue_load_test(client, monkeypatch, project_id, cases["GET"])
    monkeypatch.setattr(settings, "run_target_hosts", "localhost")
    with pytest.raises(ValueError, match="allowed host"):
        load_runner.run_load_test(db_session, load_test_id)
    assert client.get(f"/load-tests/{load_test_id}").json()["status"] == "failed"


def test_worker_records_locust_failure(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, cases = _make_cases(client)
    load_test_id = _queue_load_test(client, monkeypatch, project_id, cases["GET"])
    monkeypatch.setattr(load_runner, "TemporaryDirectory", lambda **_kwargs: nullcontext("/tmp"))
    monkeypatch.setattr(
        load_runner.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 1, "", "Locust failed"),
    )
    with pytest.raises(RuntimeError, match="Locust exited"):
        load_runner.run_load_test(db_session, load_test_id)
    summary = client.get(f"/load-tests/{load_test_id}").json()
    assert summary["status"] == "failed"
    assert "Locust failed" in summary["error_message"]


def test_queue_failure_is_stored(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, cases = _make_cases(client)

    def fail(_load_test_id: int) -> None:
        raise ConnectionError("Redis unavailable")

    monkeypatch.setattr(load_tests.execute_load_test_task, "delay", fail)
    response = client.post(
        f"/projects/{project_id}/load-tests", json={"test_case_id": cases["GET"]}
    )
    assert response.status_code == 503
    assert db_session.scalars(select(StoredLoadTest)).one().status == "failed"


def test_load_routes_return_404(client: TestClient) -> None:
    assert client.get("/projects/999/load-tests").status_code == 404
    assert client.get("/load-tests/999").status_code == 404


def test_celery_load_task_calls_runner(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def record(db: Session, load_test_id: int) -> None:
        assert db is db_session
        calls.append(load_test_id)

    monkeypatch.setitem(worker.celery_app.conf, "task_always_eager", True)
    monkeypatch.setitem(worker.celery_app.conf, "task_eager_propagates", True)
    monkeypatch.setattr(worker, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(worker, "run_load_test", record)
    worker.execute_load_test_task.delay(42)
    assert calls == [42]


def test_locust_json_parser_reads_final_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    report = [
        {
            "name": "/pets",
            "method": "GET",
            "num_requests": 20,
            "num_failures": 2,
            "total_response_time": 230,
            "response_times": {"10": 10, "15": 8, "24": 2},
        }
    ]
    monkeypatch.setattr(Path, "open", lambda self, **_kwargs: StringIO(json.dumps(report)))
    metrics = load_runner.read_locust_summary(Path("unused.json"), "/pets", 5)
    assert metrics["total_requests"] == 20
    assert metrics["failure_percentage"] == 10.0
    assert metrics["average_latency_ms"] == 11.5
    assert metrics["p95_latency_ms"] == 24.0
    assert metrics["requests_per_second"] == 4.0


def test_locust_json_parser_rejects_zero_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    report = [
        {"name": "/pets", "method": "GET", "num_requests": 0, "num_failures": 0}
    ]
    monkeypatch.setattr(Path, "open", lambda self, **_kwargs: StringIO(json.dumps(report)))
    with pytest.raises(ValueError, match="without sending a request"):
        load_runner.read_locust_summary(Path("unused.json"), "/pets", 5)


def test_locust_json_parser_rejects_wrong_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    report = [{"name": "/other", "method": "GET", "num_requests": 2}]
    monkeypatch.setattr(Path, "open", lambda self, **_kwargs: StringIO(json.dumps(report)))
    with pytest.raises(ValueError, match="selected endpoint"):
        load_runner.read_locust_summary(Path("unused.json"), "/pets", 5)
