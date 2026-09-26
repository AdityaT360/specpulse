import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import TestResult as StoredResult
from app.db.models import TestRun as StoredRun

TARGET = "http://demo-target:8001/"


def _project_with_cases(client: TestClient) -> tuple[int, int, dict[str, int]]:
    project = client.post("/projects", json={"name": "Reliability demo", "base_url": TARGET})
    assert project.status_code == 201
    project_id = project.json()["id"]
    document = {
        "openapi": "3.0.3",
        "paths": {
            "/flaky": {"get": {"responses": {"200": {}}}},
            "/steady": {"get": {"responses": {"200": {}}}},
        },
    }
    upload = client.post(
        f"/projects/{project_id}/specs",
        files={"file": ("demo.json", json.dumps(document), "application/json")},
    )
    assert upload.status_code == 201
    spec_id = upload.json()["id"]
    endpoints = client.get(f"/specs/{spec_id}/endpoints").json()
    cases = client.post(f"/specs/{spec_id}/test-cases/generate").json()
    paths = {endpoint["id"]: endpoint["path"] for endpoint in endpoints}
    case_ids = {paths[case["endpoint_id"]]: case["id"] for case in cases}
    return project_id, spec_id, case_ids


def _record_result(
    db: Session,
    project_id: int,
    spec_id: int,
    case_id: int,
    index: int,
    passed: bool,
    *,
    target: str = TARGET,
    run_status: str = "completed",
) -> None:
    run = StoredRun(
        project_id=project_id,
        spec_id=spec_id,
        target_base_url=target,
        status=run_status,
        total_tests=1,
        passed=int(passed),
        failed=int(not passed),
        finished_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
    )
    db.add(run)
    db.flush()
    db.add(
        StoredResult(
            test_run_id=run.id,
            test_case_id=case_id,
            status="passed" if passed else "failed",
            actual_status=200 if passed else 503,
            latency_ms=10.0,
        )
    )
    db.commit()


def _summary(client: TestClient, project_id: int, path: str) -> dict:
    response = client.get(f"/projects/{project_id}/reliability")
    assert response.status_code == 200
    return next(item for item in response.json() if item["path"] == path)


def test_reliability_shows_endpoints_without_history(client: TestClient) -> None:
    project_id, _, _ = _project_with_cases(client)
    response = client.get(f"/projects/{project_id}/reliability")
    assert response.status_code == 200
    assert [item["path"] for item in response.json()] == ["/flaky", "/steady"]
    for item in response.json():
        assert item["total_runs"] == 0
        assert item["failure_rate"] is None
        assert item["recent_failure_rate"] is None
        assert item["is_flaky"] is False
    assert client.get("/projects/999/reliability").status_code == 404


def test_alternating_outcomes_are_flagged(
    client: TestClient, db_session: Session
) -> None:
    project_id, spec_id, cases = _project_with_cases(client)
    for index, passed in enumerate([True, False, True, False, True, False]):
        _record_result(db_session, project_id, spec_id, cases["/flaky"], index, passed)

    summary = _summary(client, project_id, "/flaky")
    assert summary["total_runs"] == 6
    assert summary["failure_rate"] == 0.5
    assert summary["recent_runs"] == 6
    assert summary["recent_failure_rate"] == 0.5
    assert summary["flaky_score"] == 1.0
    assert summary["is_flaky"] is True
    assert summary["last_run_at"] is not None
    assert _summary(client, project_id, "/steady")["total_runs"] == 0


@pytest.mark.parametrize(
    ("outcomes", "failure_rate", "score"),
    [
        ([False] * 6, 1.0, 0.0),
        ([True] * 3 + [False] * 3, 0.5, 0.2),
        ([True, False], 0.5, 1.0),
    ],
)
def test_persistent_failure_regression_and_sparse_history_are_not_flaky(
    client: TestClient,
    db_session: Session,
    outcomes: list[bool],
    failure_rate: float,
    score: float,
) -> None:
    project_id, spec_id, cases = _project_with_cases(client)
    for index, passed in enumerate(outcomes):
        _record_result(db_session, project_id, spec_id, cases["/flaky"], index, passed)

    summary = _summary(client, project_id, "/flaky")
    assert summary["failure_rate"] == failure_rate
    assert summary["flaky_score"] == score
    assert summary["is_flaky"] is False


def test_only_last_ten_results_drive_flaky_verdict(
    client: TestClient, db_session: Session
) -> None:
    project_id, spec_id, cases = _project_with_cases(client)
    outcomes = [True, False, True, False, True] + [True] * 10
    for index, passed in enumerate(outcomes):
        _record_result(db_session, project_id, spec_id, cases["/flaky"], index, passed)

    summary = _summary(client, project_id, "/flaky")
    assert summary["total_runs"] == 15
    assert summary["failure_rate"] == pytest.approx(2 / 15)
    assert summary["recent_runs"] == 10
    assert summary["recent_failure_rate"] == 0.0
    assert summary["flaky_score"] == 0.0
    assert summary["is_flaky"] is False


def test_incomplete_runs_and_previous_targets_are_excluded(
    client: TestClient, db_session: Session
) -> None:
    project_id, spec_id, cases = _project_with_cases(client)
    _record_result(db_session, project_id, spec_id, cases["/flaky"], 0, True)
    _record_result(
        db_session, project_id, spec_id, cases["/flaky"], 1, False, run_status="failed"
    )
    _record_result(
        db_session, project_id, spec_id, cases["/flaky"], 2, False, target="http://old:8001"
    )
    summary = _summary(client, project_id, "/flaky")
    assert summary["total_runs"] == 1
    assert summary["failure_rate"] == 0.0
    assert summary["target_base_url"] == TARGET


def test_demo_endpoint_alternates_predictably() -> None:
    from examples.demo_target import app

    app.state.flaky_calls = 0
    with TestClient(app) as client:
        assert [client.get("/flaky").status_code for _ in range(5)] == [
            200,
            503,
            200,
            503,
            200,
        ]
