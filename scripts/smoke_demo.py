import time
from pathlib import Path
from uuid import uuid4

import httpx

API_URL = "http://127.0.0.1:8000"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def send(client: httpx.Client, method: str, path: str, **kwargs: object) -> object:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def upload(client: httpx.Client, project_id: int, filename: str) -> int:
    with (EXAMPLES / filename).open("rb") as file:
        spec = send(client, "POST", f"/projects/{project_id}/specs", files={"file": file})
    return spec["id"]


def wait_for(client: httpx.Client, path: str, timeout_seconds: int = 60) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        job = send(client, "GET", path)
        if job["status"] == "completed":
            return job
        if job["status"] == "failed":
            raise RuntimeError(f"{path} failed: {job['error_message']}")
        time.sleep(0.5)
    raise TimeoutError(f"{path} did not finish within {timeout_seconds} seconds")


def run() -> None:
    with httpx.Client(base_url=API_URL, timeout=15) as client:
        health = send(client, "GET", "/health")
        assert health["status"] == "ok"
        project = send(
            client,
            "POST",
            "/projects",
            json={
                "name": f"M7 demo {uuid4().hex[:8]}",
                "base_url": "http://demo-target:8001",
            },
        )
        project_id = project["id"]
        print(f"Project {project_id}: created")

        spec_id = upload(client, project_id, "sample_openapi.json")
        cases = send(client, "POST", f"/specs/{spec_id}/test-cases/generate")
        endpoints = send(client, "GET", f"/specs/{spec_id}/endpoints")
        get_endpoint_id = next(
            endpoint["id"]
            for endpoint in endpoints
            if endpoint["path"] == "/pets" and endpoint["method"] == "GET"
        )
        get_case_id = next(case["id"] for case in cases if case["endpoint_id"] == get_endpoint_id)
        print(f"Spec {spec_id}: generated {len(cases)} cases")

        run = send(
            client,
            "POST",
            f"/projects/{project_id}/test-runs",
            json={"spec_id": spec_id, "confirm_mutating_requests": True},
        )
        finished_run = wait_for(client, f"/test-runs/{run['id']}")
        results = send(client, "GET", f"/test-runs/{run['id']}/results")
        assert len(results) == len(cases)
        assert finished_run["failed"] == 0
        print(f"Regression run {run['id']}: {finished_run['passed']} passed")

        flaky_spec_id = upload(client, project_id, "flaky_openapi.json")
        send(client, "POST", f"/specs/{flaky_spec_id}/test-cases/generate")
        for _ in range(5):
            flaky_run = send(
                client,
                "POST",
                f"/projects/{project_id}/test-runs",
                json={"spec_id": flaky_spec_id},
            )
            wait_for(client, f"/test-runs/{flaky_run['id']}")
        reliability = send(client, "GET", f"/projects/{project_id}/reliability")
        flaky = next(row for row in reliability if row["path"] == "/flaky")
        assert flaky["is_flaky"]
        print(f"Flaky endpoint: score {flaky['flaky_score']}")

        load = send(
            client,
            "POST",
            f"/projects/{project_id}/load-tests",
            json={"test_case_id": get_case_id, "users": 1, "duration_seconds": 5},
        )
        summary = wait_for(client, f"/load-tests/{load['id']}")
        assert summary["total_requests"] > 0
        assert summary["failures"] == 0
        print(
            f"Load test {load['id']}: {summary['total_requests']} requests, "
            f"{summary['p95_latency_ms']} ms p95, {summary['requests_per_second']} req/s"
        )
        print("SpecPulse smoke demo passed")


if __name__ == "__main__":
    run()
