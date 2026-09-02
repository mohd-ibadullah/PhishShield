#!/usr/bin/env python3
"""T12: 16×50 concurrency probe against local uvicorn."""
from __future__ import annotations

import asyncio
import time
import statistics

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
    errors = {}
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
    errs = [r[2] for r in results if r[2]]

    for e in errs:
        errors[e] = errors.get(e, 0) + 1

    p50 = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    rps = n / wall
    mean = statistics.mean(times)

    # Self-check: wall ≈ sum_of_all_times / concurrency (parallel execution)
    total_time = sum(times)
    expected = total_time / CONCURRENCY
    ratio = wall / expected if expected > 0 else 0

    print(f"n={n} wall={wall:.2f}s rps={rps:.1f} p50={p50:.3f}s p95={p95:.3f}s errors={errors}")
    print(f"self-check: total_time={total_time:.2f}s, expected_wall={expected:.2f}s, ratio={ratio:.2f}")


if __name__ == "__main__":
    asyncio.run(run_load())
