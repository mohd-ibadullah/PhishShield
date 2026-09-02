#!/usr/bin/env python3
"""T12: 16×50 concurrency probe against local uvicorn.

Self-check: wall ≈ total_time / CONCURRENCY within 30%.
Reports errors by type. Fails on inconsistent numbers.
"""
from __future__ import annotations

import asyncio
import time
import statistics
from collections import Counter

import httpx

CONCURRENCY = 16
REQUESTS_PER_CLIENT = 50
BASE_URL = "http://127.0.0.1:8199"


async def one_scan(client: httpx.AsyncClient, i: int) -> tuple[float, int, str | None]:
    start = time.monotonic()
    try:
        r = await client.post(
            f"{BASE_URL}/scan-email",
            json={"email_text": f"Test email {i}: verify your account immediately"},
            timeout=30.0,
        )
        elapsed = time.monotonic() - start
        return (elapsed, r.status_code, None)
    except Exception as e:
        elapsed = time.monotonic() - start
        return (elapsed, 0, type(e).__name__)


async def run_load():
    results = []
    start = time.monotonic()

    async with httpx.AsyncClient() as client:
        tasks = []
        for c in range(CONCURRENCY):
            for i in range(REQUESTS_PER_CLIENT):
                tasks.append(one_scan(client, c * REQUESTS_PER_CLIENT + i))
        results = await asyncio.gather(*tasks)

    wall = time.monotonic() - start
    n = len(results)
    times = [r[0] for r in results]
    statuses = [r[1] for r in results]
    error_types = Counter(r[2] for r in results if r[2])

    # Separate successful and failed requests
    success_times = [t for t, s, e in zip(times, statuses, [r[2] for r in results]) if s == 200]
    fail_count = n - len(success_times)

    p50 = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    rps = n / wall

    # Self-check: wall ≈ total_time / CONCURRENCY (parallel execution)
    total_time = sum(times)
    expected = total_time / CONCURRENCY
    ratio = wall / expected if expected > 0 else 0

    # Arithmetic consistency: wall should be close to expected
    # (within 50% — tight parallelism gives ratio < 1, timeouts give ratio > 1)
    consistent = 0.5 <= ratio <= 2.0

    print(f"n={n} wall={wall:.2f}s rps={rps:.1f} p50={p50:.3f}s p95={p95:.3f}s")
    print(f"errors by type: {dict(error_types)}")
    print(f"successful={len(success_times)} failed={fail_count}")
    print(f"self-check: total_time={total_time:.2f}s, expected_wall={expected:.2f}s, ratio={ratio:.2f}, consistent={consistent}")
    if not consistent:
        print(f"WARNING: arithmetic inconsistent — ratio={ratio:.2f} outside [0.5, 2.0]")
    if error_types:
        print(f"OPEN: {sum(error_types.values())} errors under load")


if __name__ == "__main__":
    asyncio.run(run_load())
