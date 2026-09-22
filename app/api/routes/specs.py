from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DbSession
from app.db.models import Endpoint, Project, UploadedSpec
from app.schemas.spec import EndpointRead, UploadedSpecRead
from app.services.openapi_parser import (
    ALLOWED_SPEC_EXTENSIONS,
    MAX_SPEC_BYTES,
    OpenAPISpecError,
    parse_openapi,
)

router = APIRouter()
SpecFile = Annotated[UploadFile, File(description="OpenAPI 3.x JSON or YAML file")]


@router.post(
    "/projects/{project_id}/specs",
    response_model=UploadedSpecRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_spec(project_id: int, file: SpecFile, db: DbSession) -> UploadedSpecRead:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in ALLOWED_SPEC_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a .json, .yaml, or .yml file.",
        )

    content = await file.read(MAX_SPEC_BYTES + 1)
    await file.close()
    if len(content) > MAX_SPEC_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="OpenAPI files must be 1 MB or smaller.",
        )

    try:
        parsed = parse_openapi(content, filename)
    except OpenAPISpecError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    uploaded_spec = UploadedSpec(
        project_id=project_id,
        filename=filename,
        openapi_version=parsed.version,
        raw_spec=parsed.document,
    )
    db.add(uploaded_spec)

    try:
        db.flush()
        db.add_all(
            Endpoint(
                spec_id=uploaded_spec.id,
                path=item.path,
                method=item.method,
                operation_id=item.operation_id,
                summary=item.summary,
                parameters=item.parameters,
                request_body=item.request_body,
                responses=item.responses,
                has_request_body=item.request_body is not None,
            )
            for item in parsed.endpoints
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The OpenAPI spec could not be stored.",
        ) from exc

    db.refresh(uploaded_spec)
    return _spec_response(uploaded_spec, len(parsed.endpoints))


@router.get("/projects/{project_id}/specs", response_model=list[UploadedSpecRead])
def list_specs(project_id: int, db: DbSession) -> list[UploadedSpecRead]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    rows = db.execute(
        select(UploadedSpec, func.count(Endpoint.id))
        .outerjoin(Endpoint)
        .where(UploadedSpec.project_id == project_id)
        .group_by(UploadedSpec.id)
        .order_by(UploadedSpec.created_at.desc())
    ).all()
    return [_spec_response(spec, endpoint_count) for spec, endpoint_count in rows]


@router.get("/specs/{spec_id}/endpoints", response_model=list[EndpointRead])
def list_endpoints(spec_id: int, db: DbSession) -> list[Endpoint]:
    if db.get(UploadedSpec, spec_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spec not found.")

    return list(
        db.scalars(
            select(Endpoint)
            .where(Endpoint.spec_id == spec_id)
            .order_by(Endpoint.path, Endpoint.method)
        )
    )


def _spec_response(spec: UploadedSpec, endpoint_count: int) -> UploadedSpecRead:
    return UploadedSpecRead(
        id=spec.id,
        project_id=spec.project_id,
        filename=spec.filename,
        openapi_version=spec.openapi_version,
        endpoint_count=endpoint_count,
        created_at=spec.created_at,
    )
