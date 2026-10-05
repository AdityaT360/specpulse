from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.db.models import Endpoint, LoadTest, Project, TestCase, UploadedSpec
from app.schemas.load_test import LoadTestCreate, LoadTestRead
from app.services.test_runner import TargetNotAllowed, validate_target
from app.worker import execute_load_test_task

router = APIRouter()


@router.post(
    "/projects/{project_id}/load-tests",
    response_model=LoadTestRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_load_test(project_id: int, payload: LoadTestCreate, db: DbSession) -> LoadTest:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if not project.base_url:
        raise HTTPException(status_code=422, detail="Set a project base_url first.")
    try:
        validate_target(project.base_url)
    except TargetNotAllowed as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    case_row = db.execute(
        select(TestCase, Endpoint)
        .join(Endpoint, TestCase.endpoint_id == Endpoint.id)
        .join(UploadedSpec, Endpoint.spec_id == UploadedSpec.id)
        .where(TestCase.id == payload.test_case_id, UploadedSpec.project_id == project_id)
    ).one_or_none()
    if case_row is None:
        raise HTTPException(status_code=404, detail="Test case not found in this project.")
    case, endpoint = case_row
    if endpoint.method != "GET" or case.headers:
        raise HTTPException(status_code=422, detail="Choose a GET case without custom headers.")
    if db.scalar(
        select(LoadTest.id).where(LoadTest.status.in_(["queued", "running"])).limit(1)
    ) is not None:
        raise HTTPException(status_code=409, detail="Another load test is already active.")

    load_test = LoadTest(
        project_id=project_id,
        test_case_id=case.id,
        target_base_url=project.base_url,
        users=payload.users,
        spawn_rate=payload.spawn_rate,
        duration_seconds=payload.duration_seconds,
        status="queued",
    )
    db.add(load_test)
    db.commit()
    db.refresh(load_test)
    try:
        execute_load_test_task.delay(load_test.id)
    except Exception as exc:
        load_test.status = "failed"
        load_test.error_message = "The load-test queue is unavailable."
        load_test.finished_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(status_code=503, detail=load_test.error_message) from exc
    return load_test


@router.get("/projects/{project_id}/load-tests", response_model=list[LoadTestRead])
def list_load_tests(project_id: int, db: DbSession) -> list[LoadTest]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return list(
        db.scalars(
            select(LoadTest)
            .where(LoadTest.project_id == project_id)
            .order_by(LoadTest.created_at.desc(), LoadTest.id.desc())
        )
    )


@router.get("/load-tests/{load_test_id}", response_model=LoadTestRead)
def get_load_test(load_test_id: int, db: DbSession) -> LoadTest:
    load_test = db.get(LoadTest, load_test_id)
    if load_test is None:
        raise HTTPException(status_code=404, detail="Load test not found.")
    return load_test
