# SpecPulse Architecture

This document describes the current M5 architecture and the planned direction for later milestones.

## System Overview

SpecPulse currently runs as a local Docker Compose stack:

```mermaid
flowchart LR
    U["Developer / Swagger UI"] --> A["FastAPI routes"]
    A --> V["OpenAPI parser"]
    A --> G["Test case generator"]
    V --> P["PostgreSQL"]
    G --> P
    A --> R["Redis broker"]
    R --> W["Celery worker"]
    W --> P
    W --> D["Demo target / allowed local API"]
    A --> S["Reliability summary"]
    S --> P
```

## Components

### FastAPI App

The API layer exposes health, project, OpenAPI upload, test-case, and test-run APIs. FastAPI validates route inputs and provides Swagger UI for local demos. Starting a run creates a queued database record, then publishes its ID to Redis.

### OpenAPI Parser

The parser accepts UTF-8 JSON, YAML, and YML files up to 1 MB. It extracts operations from OpenAPI 3.x `paths`, resolves local parameter references, and applies operation-level parameter overrides. It is not a full OpenAPI validator; Path Item references are rejected for now. Parsing happens before any database writes.

### Test Case Generator

The generator makes one draft success case per endpoint. It selects the lowest explicit `2xx` response code (or assumes `200`), fills required path/query/header parameters, and builds basic JSON bodies from examples or required schema properties. Local `$ref` values are resolved. Unsupported schemas fail the whole generation request with `422` and no partial insert. Drafts are generated once per spec; execution requires a separate request.

### Test Runner

The Celery worker claims a queued run, rechecks the configured target allowlist, then calls each case with HTTPX. It records actual status, latency, and errors even when a target request fails. Redirects and environment proxies are disabled. A run moves through `queued`, `running`, and `completed` or `failed`; individual result failures still leave the run `completed` so all cases can be inspected.

### Reliability Summary

The summary reads completed results for the project's current target, grouped by endpoint ID. It shows lifetime failure rate and a rolling window of ten outcomes. The flaky score is the fraction of adjacent outcomes that changed; a flaky verdict also requires at least five results, mixed outcomes, a 10-90% recent failure rate, and two changes. No extra table or migration is needed, so the view cannot drift from stored results. A larger installation would move the aggregation into indexed/windowed queries or a materialized view.

### PostgreSQL

PostgreSQL stores projects, uploaded specs, endpoints, generated cases, runs, and results. Later milestones will add reliability summaries.

### Redis

Redis carries Celery tasks from the API to the worker. The local Compose service uses AOF persistence. PostgreSQL remains the source of truth for run status and results; there is no separate Celery result backend.

### Alembic

Alembic manages database schema migrations. M4 adds `test_runs` and `test_results`.

## Current Data Model

```mermaid
erDiagram
    PROJECTS {
        int id PK
        string name
        text description
        string base_url
        datetime created_at
    }
    UPLOADED_SPECS {
        int id PK
        int project_id FK
        string filename
        string openapi_version
        json raw_spec
        datetime created_at
    }
    ENDPOINTS {
        int id PK
        int spec_id FK
        string path
        string method
        string operation_id
        json parameters
        json request_body
        json responses
        boolean has_request_body
        datetime created_at
    }
    TEST_CASES {
        int id PK
        int endpoint_id FK
        string name
        int expected_status
        json path_params
        json query_params
        json headers
        json request_payload
        datetime created_at
    }
    TEST_RUNS {
        int id PK
        int project_id FK
        int spec_id FK
        string target_base_url
        string status
        int total_tests
        int passed
        int failed
    }
    TEST_RESULTS {
        int id PK
        int test_run_id FK
        int test_case_id FK
        string status
        int actual_status
        float latency_ms
        string error_message
    }

    PROJECTS ||--o{ UPLOADED_SPECS : contains
    UPLOADED_SPECS ||--o{ ENDPOINTS : describes
    ENDPOINTS ||--o| TEST_CASES : generates
    PROJECTS ||--o{ TEST_RUNS : owns
    UPLOADED_SPECS ||--o{ TEST_RUNS : runs
    TEST_RUNS ||--o{ TEST_RESULTS : contains
    TEST_CASES ||--o{ TEST_RESULTS : produces
```

## Request Flow: Upload Spec

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Parser as OpenAPI parser
    participant DB as PostgreSQL

    Client->>API: POST /projects/{id}/specs
    API->>API: Check project, extension, and size
    API->>Parser: Parse JSON or YAML
    Parser-->>API: Version and endpoint metadata
    API->>DB: Insert spec and endpoints
    DB-->>API: Commit transaction
    API-->>Client: 201 UploadedSpecRead
```

## Design Choices

- FastAPI gives automatic Swagger docs, which makes demos easy.
- PostgreSQL is used from the start because later reliability and reporting features need relational queries.
- Parsed documents are normalized into JSON so JSON and YAML uploads follow the same storage path.
- Endpoint metadata is stored separately so generation can use normalized operations.
- Execution is opt-in. Mutating methods need another explicit flag, and only configured local hosts may be called.
- Redis queues work; PostgreSQL records the durable outcome. A task claim prevents duplicate execution after a completed run.
- Queue publication and database commit are not atomic; a process failure between them can strand a queued run. See ADR 0005.
- Reliability is a signal based on outcomes, not a diagnosis. Persistent failures and one-time regressions are deliberately not called flaky.
- Alembic is included early to keep schema changes disciplined.
- The frontend is intentionally deferred. Swagger UI is enough for M1 demos.

## Next Architecture Additions

Possible extensions:

- Locust load-test integration
- PostgreSQL-backed integration checks in CI
