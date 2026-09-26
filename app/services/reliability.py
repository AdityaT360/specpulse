from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Endpoint, TestCase, TestResult, TestRun, UploadedSpec
from app.schemas.reliability import EndpointReliabilityRead

WINDOW_SIZE = 10
MIN_RUNS_FOR_FLAKY = 5


@dataclass
class _History:
    total_runs: int = 0
    failures: int = 0
    recent: deque[str] = field(default_factory=lambda: deque(maxlen=WINDOW_SIZE))
    last_run_at: datetime | None = None


def summarize_reliability(
    db: Session, project_id: int, target_base_url: str | None
) -> list[EndpointReliabilityRead]:
    endpoints = db.scalars(
        select(Endpoint)
        .join(UploadedSpec, Endpoint.spec_id == UploadedSpec.id)
        .where(UploadedSpec.project_id == project_id)
        .order_by(Endpoint.path, Endpoint.method, Endpoint.id)
    ).all()

    histories: dict[int, _History] = defaultdict(_History)
    if target_base_url:
        rows = db.execute(
            select(TestCase.endpoint_id, TestResult.status, TestRun.finished_at)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .join(Endpoint, TestCase.endpoint_id == Endpoint.id)
            .join(UploadedSpec, Endpoint.spec_id == UploadedSpec.id)
            .join(TestRun, TestResult.test_run_id == TestRun.id)
            .where(
                UploadedSpec.project_id == project_id,
                TestRun.project_id == project_id,
                TestRun.target_base_url == target_base_url,
                TestRun.status == "completed",
            )
            .order_by(TestRun.finished_at, TestRun.id, TestResult.id)
        )
        for endpoint_id, status, finished_at in rows:
            history = histories[endpoint_id]
            history.total_runs += 1
            history.failures += status == "failed"
            history.recent.append(status)
            history.last_run_at = finished_at

    summaries = []
    for endpoint in endpoints:
        history = histories[endpoint.id]
        recent = list(history.recent)
        recent_failures = recent.count("failed")
        transitions = sum(before != after for before, after in pairwise(recent))
        recent_rate = recent_failures / len(recent) if recent else None
        summaries.append(
            EndpointReliabilityRead(
                endpoint_id=endpoint.id,
                spec_id=endpoint.spec_id,
                method=endpoint.method,
                path=endpoint.path,
                target_base_url=target_base_url,
                total_runs=history.total_runs,
                failure_rate=(
                    history.failures / history.total_runs if history.total_runs else None
                ),
                recent_runs=len(recent),
                recent_failure_rate=recent_rate,
                flaky_score=transitions / (len(recent) - 1) if len(recent) > 1 else 0.0,
                is_flaky=(
                    len(recent) >= MIN_RUNS_FOR_FLAKY
                    and recent_rate is not None
                    and 0.1 <= recent_rate <= 0.9
                    and transitions >= 2
                ),
                last_run_at=history.last_run_at,
            )
        )
    return summaries
