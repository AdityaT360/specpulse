# SpecPulse

SpecPulse is an OpenAPI test intelligence platform. It parses OpenAPI specs into endpoint metadata that later milestones will use to generate and run API tests.

This repository currently contains **M2: OpenAPI upload and endpoint parsing**, built on the M1 FastAPI and PostgreSQL foundation.

## Current Features

- FastAPI application
- Health endpoint
- Project create/list/detail endpoints
- OpenAPI 3.x JSON and YAML upload
- 1 MB upload limit and structured validation errors
- Extraction of paths, methods, parameters, request bodies, and responses
- Uploaded spec and endpoint persistence
- Spec and endpoint listing APIs
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
```

## Next Milestone

M3 will add:

- Generated test cases for parsed endpoints
- Default success status selection
- Basic request payload and parameter values
