from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Project
from app.db.session import get_db
from app.schemas.project import ProjectCreate, ProjectRead

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: DbSession) -> Project:
    project = Project(
        name=payload.name,
        description=payload.description,
        base_url=str(payload.base_url) if payload.base_url else None,
    )
    db.add(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A project with this name already exists.",
        ) from exc

    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(db: DbSession) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: DbSession) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project
