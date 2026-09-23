# SpecPulse

SpecPulse parses OpenAPI specs, generates draft API tests, and runs them in a background worker against an approved local target.

This repository currently contains **M4: asynchronous test execution**.

## Current Features

- FastAPI application
- Health endpoint
- Project create/list/detail endpoints
- OpenAPI 3.x JSON and YAML upload
- 1 MB upload limit and structured validation errors
- Extraction of paths, methods, parameters, request bodies, and responses
- Uploaded spec and endpoint persistence
- Spec and endpoint listing APIs
- One stored success-case draft per endpoint, including required parameter values and JSON body samples
- Clear errors for unsupported schema shapes instead of silently creating unusable cases
- Explicit test-run requests, queued execution, and stored pass/fail results
- Per-case HTTP status, latency, and error details
- Local target allowlist, request timeout, no redirects, and confirmation for mutating methods
- PostgreSQL database
- SQLAlchemy models and Alembic migrations
- Redis-backed Celery worker
- Small demo target API for repeatable local runs
- Docker Compose local stack
- pytest coverage for projects, parsing, uploads, and endpoint retrieval

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
```

## Next Milestone

M5 will add:

- Reliability summaries and flaky endpoint detection from repeated runs
