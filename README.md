# SpecPulse

SpecPulse parses OpenAPI specs, generates draft API tests, runs them against an approved local target, and summarizes the results.

This repository currently contains **M5: reliability summaries**.

## Current Features

- OpenAPI 3.x JSON/YAML upload, endpoint extraction, and stored success-case drafts
- Explicit Celery/Redis test runs with per-case status, latency, and error history
- Reliability summaries over completed runs, with a rolling flaky signal
- PostgreSQL, SQLAlchemy, Alembic, and a local Docker Compose stack
- Local target allowlist, request timeout, no redirects, and confirmation for mutating methods
- A repeatable demo target, pytest coverage, and GitHub Actions checks

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
- PyYAML
- PostgreSQL
- Redis
- Celery
- HTTPX
- Docker Compose
- pytest
- Ruff

## Quick Start

From this folder:

```powershell
docker compose up --build
```

Open:

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Try The Project API

Create a project:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/projects `
  -ContentType "application/json" `
  -Body '{"name":"Demo API","description":"First SpecPulse project","base_url":"http://demo-target:8001"}'
```

List projects:

```powershell
Invoke-RestMethod -Method Get -Uri http://localhost:8000/projects
```

Upload the included JSON example after creating project `1`:

```powershell
curl.exe -X POST `
  -F "file=@examples/sample_openapi.json" `
  http://localhost:8000/projects/1/specs
```

List its parsed endpoints, replacing `1` with the returned spec ID:

```powershell
Invoke-RestMethod -Method Get -Uri http://localhost:8000/specs/1/endpoints
```

Generate and inspect draft cases for that spec:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/specs/1/test-cases/generate
Invoke-RestMethod -Method Get -Uri http://localhost:8000/specs/1/test-cases
```

Generation is repeatable: calling it again returns the same stored cases. It does not send HTTP requests. The generator handles simple parameter schemas, JSON request bodies, and local schema references. Unsupported inputs return `422` without storing partial cases. If no explicit `2xx` response is defined, the draft assumes `200`; review that value before execution.

Start a run after inspecting the cases. Replace `1` with your project and spec IDs:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/projects/1/test-runs `
  -ContentType "application/json" `
  -Body '{"spec_id":1,"confirm_mutating_requests":true}'
```

The response is `202` with a run ID. Check its progress and results:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/test-runs/1
Invoke-RestMethod -Uri http://localhost:8000/test-runs/1/results
```

The included spec has a POST case, so it needs `confirm_mutating_requests=true`. The Docker setup permits only `demo-target` as a destination. Do not point this runner at a production API; generated POST/PUT/PATCH/DELETE requests can change data. The worker checks the allowlist again before execution and does not follow redirects. Runs are limited to 25 cases with a five-second timeout per request.

Compose keeps PostgreSQL and Redis on its internal network, so it will not compete with local services on ports 5432 or 6379.

## Reliability Demo

Upload `examples/flaky_openapi.json` to the same project, generate its case, then start five runs with that spec ID. The local `/flaky` endpoint alternates between `200` and `503`. Check the summary after the runs finish:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/projects/1/reliability
```

Each endpoint has its own history. `failure_rate` covers all completed runs against the project's current target. `recent_failure_rate` and `flaky_score` use at most the last ten results; the score is the fraction of adjacent outcomes that changed. `is_flaky` requires at least five recent results, both passes and failures, a 10-90% recent failure rate, and at least two changes. A persistent failure or one-time regression is not marked flaky. This is a useful signal, not proof of a flaky implementation; target changes and small samples can still mislead.

## Local Development Without Docker

Use Python **3.11 or 3.12** for local development. The Docker image uses Python 3.12.

Create and activate a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Run tests:

```powershell
pytest
```

Run lint:

```powershell
ruff check .
```

For local non-Docker API development, you need PostgreSQL, Redis, and matching `DATABASE_URL` and `REDIS_URL`. The default target allowlist is `localhost,127.0.0.1`; Docker uses `RUN_TARGET_HOSTS=demo-target` from `.env.example`. Run migrations and start a worker separately:

```powershell
alembic upgrade head
celery -A app.worker.celery_app worker --loglevel=info --pool=solo
```

## API Endpoints

```text
GET  /health
POST /projects
GET  /projects
GET  /projects/{project_id}
POST /projects/{project_id}/specs
GET  /projects/{project_id}/specs
GET  /specs/{spec_id}/endpoints
POST /specs/{spec_id}/test-cases/generate
GET  /specs/{spec_id}/test-cases
POST /projects/{project_id}/test-runs
GET  /projects/{project_id}/test-runs
GET  /test-runs/{run_id}
GET  /test-runs/{run_id}/results
GET  /projects/{project_id}/reliability
```

## Next Steps

Verify the complete Compose flow with PostgreSQL and Redis, then move to LogShield. Load testing is an optional extension after both core projects work.
