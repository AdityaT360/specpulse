# ADR 0003: Use Docker Compose For Local Development

## Status

Accepted

## Context

The project should be easy to run locally without paid cloud services.

## Decision

Use Docker Compose to run the API, PostgreSQL, and Redis.

## Consequences

Docker Compose gives a reproducible local environment and keeps the project free to build. The tradeoff is that it is not a full production deployment model.
