import re
from datetime import UTC, datetime
from time import perf_counter
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Endpoint, TestCase, TestResult, TestRun

MAX_CASES_PER_RUN = 25
REQUEST_TIMEOUT_SECONDS = 5
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class TargetNotAllowed(ValueError):
    pass


def validate_target(base_url: str) -> None:
    if "\\" in base_url or any(char.isspace() for char in base_url):
        raise TargetNotAllowed("Target URL contains invalid characters.")
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError as exc:
        raise TargetNotAllowed("Target URL is invalid.") from exc

    allowed_hosts = {host.strip().lower() for host in settings.run_target_hosts.split(",")}
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.hostname.lower() not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or port == 0
    ):
        raise TargetNotAllowed("Target must use an allowed host and HTTP(S), without credentials.")


def execute_test_run(db: Session, run_id: int, client: httpx.Client) -> None:
    claimed = db.execute(
        update(TestRun)
        .where(TestRun.id == run_id, TestRun.status == "queued")
        .values(status="running", started_at=datetime.now(UTC))
    )
    db.commit()
    if claimed.rowcount != 1:
        return

    run = db.get(TestRun, run_id)
    try:
        validate_target(run.target_base_url)
        cases = db.execute(
            select(TestCase, Endpoint)
            .join(Endpoint, TestCase.endpoint_id == Endpoint.id)
            .where(Endpoint.spec_id == run.spec_id)
            .order_by(Endpoint.path, Endpoint.method)
        ).all()
        if len(cases) != run.total_tests:
            raise ValueError("The generated cases changed after this run was queued.")

        for case, endpoint in cases:
            result = _execute_case(run, case, endpoint, client)
            db.add(result)
            if result.status == "passed":
                run.passed += 1
            else:
                run.failed += 1
            db.commit()

        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        db.commit()
    except Exception as exc:
        db.rollback()
        run = db.get(TestRun, run_id)
        run.status = "failed"
        run.error_message = str(exc)[:500]
        run.finished_at = datetime.now(UTC)
        db.commit()
        raise


def _execute_case(
    run: TestRun, case: TestCase, endpoint: Endpoint, client: httpx.Client
) -> TestResult:
    started = perf_counter()
    actual_status = None
    error_message = None
    try:
        if endpoint.method not in ALLOWED_METHODS:
            raise ValueError(f"Method {endpoint.method} is not allowed for execution.")
        url = _case_url(run.target_base_url, endpoint.path, case.path_params)
        response = client.request(
            endpoint.method,
            url,
            params=case.query_params,
            headers=case.headers,
            json=case.request_payload,
        )
        actual_status = response.status_code
        if actual_status != case.expected_status:
            error_message = f"Expected HTTP {case.expected_status}, got {actual_status}."
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        error_message = str(exc)[:500]

    return TestResult(
        test_run_id=run.id,
        test_case_id=case.id,
        status="failed" if error_message else "passed",
        actual_status=actual_status,
        latency_ms=round((perf_counter() - started) * 1000, 2),
        error_message=error_message,
    )


def _case_url(base_url: str, path: str, path_params: dict[str, object]) -> str:
    if not path.startswith("/") or "?" in path or "#" in path or "\\" in path:
        raise ValueError("The endpoint path is not safe to execute.")
    missing = set(re.findall(r"\{([^{}]+)\}", path)) - path_params.keys()
    if missing:
        raise ValueError(f"Missing path parameters: {', '.join(sorted(missing))}.")
    for name, value in path_params.items():
        path = path.replace("{" + name + "}", quote(str(value), safe=""))
    base = urlsplit(base_url)
    return urlunsplit((base.scheme, base.netloc, base.path.rstrip("/") + path, "", ""))
