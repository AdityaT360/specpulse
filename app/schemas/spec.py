from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class UploadedSpecRead(BaseModel):
    id: int
    project_id: int
    filename: str
    openapi_version: str
    endpoint_count: int
    created_at: datetime


class EndpointRead(BaseModel):
    id: int
    spec_id: int
    path: str
    method: str
    operation_id: str | None
    summary: str | None
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any] | None
    responses: dict[str, Any]
    has_request_body: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
