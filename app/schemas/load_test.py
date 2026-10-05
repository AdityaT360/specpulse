from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoadTestCreate(BaseModel):
    test_case_id: int
    users: int = Field(default=2, ge=1, le=5)
    spawn_rate: int = Field(default=1, ge=1, le=5)
    duration_seconds: int = Field(default=10, ge=5, le=30)


class LoadTestRead(BaseModel):
    id: int
    project_id: int
    test_case_id: int
    target_base_url: str
    users: int
    spawn_rate: int
    duration_seconds: int
    status: str
    total_requests: int | None
    failures: int | None
    failure_percentage: float | None
    average_latency_ms: float | None
    p95_latency_ms: float | None
    requests_per_second: float | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
