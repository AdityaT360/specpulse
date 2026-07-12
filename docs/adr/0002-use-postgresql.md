# ADR 0002: Use PostgreSQL For Persistent Storage

## Status

Accepted

## Context

SpecPulse will store projects, uploaded specs, parsed endpoints, generated test cases, test runs, and historical results.

## Decision

Use PostgreSQL as the primary database.

## Consequences

PostgreSQL supports relational modeling, indexes, and aggregation queries that will be useful for reliability reporting. The tradeoff is that local development needs a database service, which Docker Compose solves.
