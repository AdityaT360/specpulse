from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TestCaseRead(BaseModel):
    id: int
    endpoint_id: int
    name: str
    expected_status: int
    path_params: dict[str, Any]
    query_params: dict[str, Any]
    headers: dict[str, Any]
    request_payload: Any | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
