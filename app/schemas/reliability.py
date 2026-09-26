from datetime import datetime

from pydantic import BaseModel


class EndpointReliabilityRead(BaseModel):
    endpoint_id: int
    spec_id: int
    method: str
    path: str
    target_base_url: str | None
    total_runs: int
    failure_rate: float | None
    recent_runs: int
    recent_failure_rate: float | None
    flaky_score: float
    is_flaky: bool
    last_run_at: datetime | None
