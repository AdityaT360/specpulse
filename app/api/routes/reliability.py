from fastapi import APIRouter, HTTPException

from app.api.dependencies import DbSession
from app.db.models import Project
from app.schemas.reliability import EndpointReliabilityRead
from app.services.reliability import summarize_reliability

router = APIRouter()


@router.get("/projects/{project_id}/reliability", response_model=list[EndpointReliabilityRead])
def get_reliability(project_id: int, db: DbSession) -> list[EndpointReliabilityRead]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return summarize_reliability(db, project_id, project.base_url)
