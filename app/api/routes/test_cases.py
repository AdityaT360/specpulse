from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DbSession
from app.db.models import Endpoint, TestCase, UploadedSpec
from app.schemas.test_case import TestCaseRead
from app.services.test_case_generator import TestCaseGenerationError, generate_test_case

router = APIRouter()


@router.post("/specs/{spec_id}/test-cases/generate", response_model=list[TestCaseRead])
def generate_cases(spec_id: int, db: DbSession) -> list[TestCase]:
    spec = db.get(UploadedSpec, spec_id)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spec not found.")

    existing = _list_cases(spec_id, db)
    if existing:
        return existing

    endpoints = db.scalars(
        select(Endpoint).where(Endpoint.spec_id == spec_id).order_by(Endpoint.path, Endpoint.method)
    ).all()
    try:
        cases = [generate_test_case(endpoint, spec.raw_spec) for endpoint in endpoints]
        db.add_all(cases)
        db.commit()
    except TestCaseGenerationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Test cases could not be stored.",
        ) from exc
    return _list_cases(spec_id, db)


@router.get("/specs/{spec_id}/test-cases", response_model=list[TestCaseRead])
def list_cases(spec_id: int, db: DbSession) -> list[TestCase]:
    if db.get(UploadedSpec, spec_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spec not found.")
    return _list_cases(spec_id, db)


def _list_cases(spec_id: int, db: DbSession) -> list[TestCase]:
    return list(
        db.scalars(
            select(TestCase)
            .join(Endpoint)
            .where(Endpoint.spec_id == spec_id)
            .order_by(Endpoint.path, Endpoint.method)
        )
    )
