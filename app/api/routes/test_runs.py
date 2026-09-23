from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.db.models import Endpoint, Project, TestCase, TestResult, TestRun, UploadedSpec
from app.schemas.test_run import TestResultRead, TestRunCreate, TestRunRead
from app.services.test_runner import (
    ALLOWED_METHODS,
    MAX_CASES_PER_RUN,
    SAFE_METHODS,
    TargetNotAllowed,
    validate_target,
)
from app.worker import execute_test_run_task

router = APIRouter()


@router.post(
    "/projects/{project_id}/test-runs",
    response_model=TestRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_test_run(project_id: int, payload: TestRunCreate, db: DbSession) -> TestRun:
    project = db.get(Project, project_id)
    spec = db.get(UploadedSpec, payload.spec_id)
    if project is None or spec is None or spec.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project or spec not found."
        )
    if not project.base_url:
        raise HTTPException(status_code=422, detail="Set a project base_url before running tests.")
    try:
        validate_target(project.base_url)
    except TargetNotAllowed as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cases = db.execute(
        select(TestCase, Endpoint)
        .join(Endpoint, TestCase.endpoint_id == Endpoint.id)
        .where(Endpoint.spec_id == spec.id)
    ).all()
    if not cases:
        raise HTTPException(status_code=409, detail="Generate test cases before starting a run.")
    if len(cases) > MAX_CASES_PER_RUN:
        raise HTTPException(status_code=422, detail="A run can contain at most 25 cases.")
    if any(endpoint.method not in ALLOWED_METHODS for _, endpoint in cases):
        raise HTTPException(status_code=422, detail="The spec contains an unsupported HTTP method.")
    if not payload.confirm_mutating_requests and any(
        endpoint.method not in SAFE_METHODS for _, endpoint in cases
    ):
        raise HTTPException(
            status_code=422,
            detail="Set confirm_mutating_requests=true to run POST, PUT, PATCH, or DELETE cases.",
        )

    run = TestRun(
        project_id=project_id,
        spec_id=spec.id,
        target_base_url=project.base_url,
        status="queued",
        total_tests=len(cases),
        passed=0,
        failed=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        execute_test_run_task.delay(run.id)
    except Exception as exc:
        run.status = "failed"
        run.error_message = "The worker queue is unavailable."
        run.finished_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(status_code=503, detail=run.error_message) from exc
    return run


@router.get("/projects/{project_id}/test-runs", response_model=list[TestRunRead])
def list_test_runs(project_id: int, db: DbSession) -> list[TestRun]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return list(
        db.scalars(
            select(TestRun)
            .where(TestRun.project_id == project_id)
            .order_by(TestRun.created_at.desc(), TestRun.id.desc())
        )
    )


@router.get("/test-runs/{run_id}", response_model=TestRunRead)
def get_test_run(run_id: int, db: DbSession) -> TestRun:
    run = db.get(TestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found.")
    return run


@router.get("/test-runs/{run_id}/results", response_model=list[TestResultRead])
def list_test_results(run_id: int, db: DbSession) -> list[TestResult]:
    if db.get(TestRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Test run not found.")
    return list(
        db.scalars(
            select(TestResult)
            .where(TestResult.test_run_id == run_id)
            .order_by(TestResult.id)
        )
    )
