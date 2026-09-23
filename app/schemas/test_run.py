from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TestRunCreate(BaseModel):
    spec_id: int
    confirm_mutating_requests: bool = False


class TestRunRead(BaseModel):
    id: int
    project_id: int
    spec_id: int
    target_base_url: str
    status: str
    total_tests: int
    passed: int
    failed: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TestResultRead(BaseModel):
    id: int
    test_run_id: int
    test_case_id: int
    status: str
    actual_status: int | None
    latency_ms: float
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
