# ADR 0004: Normalize Uploaded OpenAPI Documents As JSON

## Status

Accepted

## Context

SpecPulse accepts both JSON and YAML OpenAPI documents. Later milestones need a consistent representation for test generation and reporting.

## Decision

Parse each upload into Python data structures and store the normalized document in a PostgreSQL JSON column. Store frequently queried operation metadata in a separate `endpoints` table.

## Consequences

JSON and YAML uploads use the same parser output and database queries. Endpoint rows make filtering and test generation straightforward. Original YAML formatting and comments are not retained, so object storage or a text column would be needed if exact source preservation becomes a requirement.
