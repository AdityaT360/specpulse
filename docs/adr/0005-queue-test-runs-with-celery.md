# ADR 0005: Queue Test Runs With Celery And Redis

## Decision

The API stores a `queued` run in PostgreSQL and sends only its ID to Celery. Redis is the broker. The worker reads cases from PostgreSQL and writes results there after each request. Celery's result backend is disabled.

## Why

Runs can take several seconds, so the API should not hold a request open while calling target services. Keeping run state in PostgreSQL makes status and results queryable through the same API, even after the worker exits. A small queue fits the local Docker Compose setup.

## Tradeoffs

Publishing to Redis and committing PostgreSQL are separate operations. If the API process stops between them, a run may remain `queued` without a task. A worker also has to tolerate duplicate delivery; it claims only runs still marked `queued`. This is suitable for the local portfolio demo, not a guarantee of exactly-once delivery. A production version would use an outbox and a recovery job for stranded runs.

Runs are restricted to approved local hosts and at most 25 cases. Mutating methods require explicit confirmation, but the user must still choose a disposable target. The runner does not follow redirects or use environment proxy settings.
