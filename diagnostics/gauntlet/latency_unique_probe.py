"""Resolve the V4.3 latency-table question with unique-marker scans.

The owner flagged that the earlier 20-call table (p50 34-38ms) looks like
in-memory cache hits, not inference. This probe runs 20 scans, every one a
unique marker, through the live /scan-email endpoint with the same session
cookie, and pastes per-call latency plus summary. No prose verdict.
"""
import http.cookiejar
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:9212"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# Mint the session cookie (same handshake the dashboard and extension use).
req = urllib.request.Request(f"{BASE}/api/session", method="POST", data=b"")
with opener.open(req, timeout=30) as resp:
    print(f"session: {resp.status}")

latencies = []
statuses = {}
for i in range(1, 21):
    marker = f"LIVE-QA-lat-{i:02d}"
    body = json.dumps({
        "email_text": f"{marker} Dear customer, your bank account is blocked. Verify your OTP now at https://sbi-kyc-{i}.xyz to avoid suspension today."
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/scan-email",
        method="POST",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    try:
        with opener.open(req, timeout=60) as resp:
            status = resp.status
            resp.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.read()
    ms = (time.perf_counter() - t0) * 1000
    latencies.append(ms)
    statuses[status] = statuses.get(status, 0) + 1
    print(f"call {i:02d} ({marker}): {status} {ms:.0f}ms")

latencies.sort()
n = len(latencies)
p50 = latencies[n // 2]
p95 = latencies[int((n - 1) * 0.95)]
print()
print(f"statuses: {statuses}")
print(f"n=20 UNIQUE markers: p50={p50:.0f}ms p95={p95:.0f}ms min={latencies[0]:.0f}ms max={latencies[-1]:.0f}ms")
