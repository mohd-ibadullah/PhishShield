"""Timestamp stability tests for /api/history.

Verifies that timestamps are stable across reads (not re-computed on each GET)
and that the scan_id is the same across reads.
"""
from __future__ import annotations

import time

import pytest


@pytest.mark.asyncio
async def test_history_timestamp_is_stable_across_reads(client):
    """Two GETs of /api/history separated by 1.1s must return byte-identical
    timestamps for the same scan. Before the fix, each GET returned datetime.now()."""
    resp = await client.post(
        "/scan-email",
        json={"email_text": "Subject: Timestamp test - body here"},
    )
    assert resp.status_code == 200

    resp1 = await client.get("/api/history")
    assert resp1.status_code == 200
    body1 = resp1.json()

    time.sleep(1.1)

    resp2 = await client.get("/api/history")
    assert resp2.status_code == 200
    body2 = resp2.json()

    assert body1 == body2, (
        "Timestamps changed between reads: "
        + str(body1[0].get("timestamp")) + " -> "
        + str(body2[0].get("timestamp"))
    )


@pytest.mark.asyncio
async def test_history_scan_id_is_stable_across_reads(client):
    """scan_id must not change between reads."""
    resp = await client.post(
        "/scan-email",
        json={"email_text": "Subject: ID stability test - body"},
    )
    assert resp.status_code == 200

    resp1 = await client.get("/api/history")
    assert resp1.status_code == 200
    id1 = resp1.json()[0]["id"] if resp1.json() else None

    resp2 = await client.get("/api/history")
    assert resp2.status_code == 200
    id2 = resp2.json()[0]["id"] if resp2.json() else None

    assert id1 == id2, f"ID changed: {id1} -> {id2}"
    assert id1 is not None, "ID is None"
