# SpecPulse

SpecPulse is an OpenAPI test intelligence platform. It will parse OpenAPI specs, generate API test cases, run tests asynchronously, store regression history, detect flaky endpoints, and summarize load-test behavior.

This repository currently contains **M1: FastAPI backend scaffold with PostgreSQL, Redis, Docker Compose, project model, health route, and project APIs**.

## Current M1 Features

- FastAPI application
- Health endpoint
- Project create/list/detail endpoints
- PostgreSQL database
- SQLAlchemy model
- Alembic initial migration
- Redis container ready for later Celery work
- Docker Compose local stack
- pytest tests for health and project APIs

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
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

## Local Development Without Docker

Use Python **3.11 or 3.12** for local development. The Docker image uses Python 3.12.

Create and activate a virtual environment:

```powershell
python -m venv .venv
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

## M1 API Endpoints

```text
GET  /health
POST /projects
GET  /projects
GET  /projects/{project_id}
```

## Next Milestone

M2 will add:

- OpenAPI file upload
- JSON/YAML parsing
- endpoint extraction
- database tables for uploaded specs and parsed endpoints

See `PROJECT_GUIDE.md` for the full one-month project plan.
