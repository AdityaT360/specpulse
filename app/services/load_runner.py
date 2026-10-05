import json
import math
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode, urlsplit, urlunsplit

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Endpoint, LoadTest, TestCase, UploadedSpec
from app.services.test_runner import case_url, validate_target

LOCUST_FILE = Path(__file__).resolve().parents[2] / "examples" / "locustfile.py"


def run_load_test(db: Session, load_test_id: int) -> None:
    claimed = db.execute(
        update(LoadTest)
        .where(LoadTest.id == load_test_id, LoadTest.status == "queued")
        .values(status="running", started_at=datetime.now(UTC))
    )
    db.commit()
    if claimed.rowcount != 1:
        return

    load_test = db.get(LoadTest, load_test_id)
    try:
        validate_target(load_test.target_base_url)
        if (
            not 1 <= load_test.users <= 5
            or not 1 <= load_test.spawn_rate <= 5
            or not 5 <= load_test.duration_seconds <= 30
        ):
            raise ValueError("Load test limits are invalid.")
        case_row = db.execute(
            select(TestCase, Endpoint)
            .join(Endpoint, TestCase.endpoint_id == Endpoint.id)
            .join(UploadedSpec, Endpoint.spec_id == UploadedSpec.id)
            .where(
                TestCase.id == load_test.test_case_id,
                UploadedSpec.project_id == load_test.project_id,
            )
        ).one_or_none()
        if case_row is None:
            raise ValueError("The selected case no longer belongs to this project.")
        case, endpoint = case_row
        if endpoint.method != "GET" or case.headers:
            raise ValueError("Load tests support GET cases without custom headers only.")

        url = case_url(load_test.target_base_url, endpoint.path, case.path_params)
        parts = urlsplit(url)
        if parts.hostname != urlsplit(load_test.target_base_url).hostname:
            raise ValueError("The generated URL left the allowed target.")
        query = urlencode(case.query_params, doseq=True)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))

        with TemporaryDirectory(prefix="specpulse-load-") as temporary_dir:
            prefix = Path(temporary_dir) / "run"
            command = [
                sys.executable,
                "-m",
                "locust",
                "-f",
                str(LOCUST_FILE),
                "--headless",
                "--users",
                str(load_test.users),
                "--spawn-rate",
                str(load_test.spawn_rate),
                "--run-time",
                f"{load_test.duration_seconds}s",
                "--host",
                load_test.target_base_url,
                "--json-file",
                str(prefix),
                "--only-summary",
                "--exit-code-on-error",
                "0",
            ]
            environment = os.environ.copy()
            environment.update(
                SPECPULSE_LOAD_URL=url,
                SPECPULSE_LOAD_NAME=endpoint.path,
                SPECPULSE_LOAD_EXPECTED_STATUS=str(case.expected_status),
            )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                env=environment,
                timeout=load_test.duration_seconds + 20,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Locust exited with code {result.returncode}: {result.stderr[-350:]}"
                )
            metrics = read_locust_summary(
                Path(f"{prefix}.json"), endpoint.path, load_test.duration_seconds
            )

        for name, value in metrics.items():
            setattr(load_test, name, value)
        load_test.status = "completed"
        load_test.finished_at = datetime.now(UTC)
        db.commit()
    except Exception as exc:
        db.rollback()
        load_test = db.get(LoadTest, load_test_id)
        load_test.status = "failed"
        load_test.error_message = str(exc)[:500]
        load_test.finished_at = datetime.now(UTC)
        db.commit()
        raise


def read_locust_summary(
    path: Path, endpoint_name: str, duration_seconds: int
) -> dict[str, int | float]:
    with path.open(encoding="utf-8") as file:
        entries = json.load(file)
    if not isinstance(entries, list):
        raise ValueError("Locust did not write a valid stats report.")
    row = next(
        (
            entry
            for entry in entries
            if entry.get("name") == endpoint_name and entry.get("method") == "GET"
        ),
        None,
    )
    if row is None:
        raise ValueError("Locust did not write stats for the selected endpoint.")

    total_requests = int(row["num_requests"])
    failures = int(row["num_failures"])
    if total_requests == 0:
        raise ValueError("Locust completed without sending a request.")
    latency_counts = sorted(
        (int(latency), count) for latency, count in row["response_times"].items()
    )
    if not latency_counts:
        raise ValueError("Locust did not write response times.")
    percentile_position = math.ceil(sum(count for _, count in latency_counts) * 0.95)
    observed = 0
    p95 = 0
    for latency, count in latency_counts:
        observed += count
        if observed >= percentile_position:
            p95 = latency
            break
    return {
        "total_requests": total_requests,
        "failures": failures,
        "failure_percentage": round(failures * 100 / total_requests, 2),
        "average_latency_ms": round(float(row["total_response_time"]) / total_requests, 2),
        "p95_latency_ms": float(p95),
        "requests_per_second": round(total_requests / duration_seconds, 2),
    }
