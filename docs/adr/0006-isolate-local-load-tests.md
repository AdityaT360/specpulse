# ADR 0006: Isolate Local Load Tests

## Decision

Run Locust in a separate single-concurrency Celery worker on the `load-tests` queue. The API accepts only a generated GET case without custom headers, an approved local target, 1-5 users, and a 5-30 second duration. The worker checks those limits again before starting the subprocess. Store the final summary in PostgreSQL.

## Why

Load testing can occupy a worker and send many requests. A separate queue keeps a load job from delaying ordinary regression runs. The narrow limits make it practical to demonstrate Locust without accidentally aiming a heavy job at a remote or production API. PostgreSQL keeps the report available after the worker exits.

## Tradeoffs

One active load job is enough for a local demo but is not a scheduling system for multiple users. The API's active-job check is not transactional, and a stopped worker can leave a job queued or running. The report stores summary metrics, not every request. Its p95 comes from Locust's rounded latency buckets, and throughput divides requests by the configured duration. A production service would need per-project quotas, job recovery, stronger network isolation, and a clearer retention policy.
