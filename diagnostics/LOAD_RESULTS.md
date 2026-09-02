# Load Test Results

## 16×50 (800 requests, 1 worker)

| Metric | Value |
|--------|-------|
| n | 800 |
| wall | 55.22s |
| rps | 14.5 |
| p50 | 36.062s |
| p95 | 50.937s |
| errors | PoolTimeout: 577 |

**Note:** High PoolTimeout count indicates connection pool saturation under 16 concurrent clients. Single-writer SQLite bottleneck suspected. WAL mode and busy_timeout not configured.

## 2 workers

NOT-RUN: requires server restart with `--workers 2` flag, which changes process model.
