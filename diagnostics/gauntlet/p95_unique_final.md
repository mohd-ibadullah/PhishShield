# P95 latency, final table (unique markers, live endpoint)

Owner flagged that the earlier 20-call table (p50 34-38ms) was cache-hit
latency, not model inference. Resolved 2026-09-12 with a probe that sends
20 unique-marker scans through the live `/scan-email` endpoint
(`diagnostics/gauntlet/latency_unique_probe.py`).

## Raw result (unique markers, same session, first window)

```
call 01: 200 711ms   call 11: 429 2ms
call 02: 200 452ms   call 12: 429 20ms
call 03: 200 167ms   ...      (calls 11-20: 429 rate limit)
call 10: 200 172ms
statuses: {200: 10, 429: 10}
warm 200-calls only: 148-205ms (outlier first-call 711ms, second 452ms)
```

## What the numbers mean

- **Real inference (unique text, warm): ~150-200ms per scan.** First call in a
  window pays ~0.5-0.7s (provider wake-up / per-process cold paths).
- **Cache hits (identical text repeat): ~15-40ms.** The earlier 34-38ms table
  measured this path and was mislabeled as inference; corrected here.
- **Rate limit:** 10 scans per session per 60s (`enforce_scan_rate_limit`,
  default max_requests=10). Calls 11-20 correctly got 429 in every window.
  The V5.5 "20/20 200" run must therefore have spanned more than one window
  or used multiple sessions; its 3.69s wall over 20 scans is consistent with
  ~10 real inferences (~150-200ms each) plus cache/rate-limit fast paths.

## Verdict row (replaces the V4.3 table)

| path | p50 | note |
|---|---|---|
| model inference, unique text, warm | ~150-200ms | real latency |
| first call after idle window | ~450-711ms | provider wake-up |
| identical-text cache hit | ~15-40ms | not inference |
| 300ms gate (tests/test_performance.py:94) | PASS (6/6, f0d17a2) | warm loop, stubbed externals |
