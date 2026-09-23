# SpecPulse

SpecPulse is an OpenAPI test intelligence platform. It parses OpenAPI specs and generates draft API test cases. Running those cases against a target service is the next milestone.

This repository currently contains **M3: test case generation**, built on the M1 and M2 foundation.

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
- PostgreSQL database
- SQLAlchemy models and Alembic migrations
- Redis container ready for later Celery work
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
  -Body '{"name":"Demo API","description":"First SpecPulse project","base_url":"https://example.com"}'
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

For local non-Docker API development, you still need a PostgreSQL instance and a matching `DATABASE_URL`.

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
```

## Next Milestone

M4 will add:

- A Celery worker and Redis-backed execution queue
- Explicit run requests and stored results
- Safeguards around which target URLs may be called
