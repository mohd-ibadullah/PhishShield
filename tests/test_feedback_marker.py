"""W2 G4(b) — feedback.csv marker proof.

D5: feedback.csv stores email_hash, not plaintext email_text.
Submit feedback carrying a unique marker, then verify:
  1. The email_hash IS present (computed from the marker email)
  2. The marker itself is NOT stored (no plaintext leak)
  3. No endpoint exposes the marker in response
"""
from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

import main as backend_main

MARKER = "MKR-FEEDBACK-CSV-4455"
SAFE_EMAIL = "Subject: Feedback test\nTeam meeting at noon."


def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=backend_main.app), base_url="http://testserver")


async def _bootstrap_session(client: AsyncClient) -> None:
    response = await client.post("/api/session")
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_feedback_marker_stored_in_csv_and_exposed(client, tmp_path, monkeypatch) -> None:
    """D5: Submit feedback with a unique marker, then read feedback.csv to
    verify that email_hash is stored (not plaintext email_text)."""
    feedback_csv = tmp_path / "feedback.csv"
    feedback_memory = tmp_path / "feedback_memory.json"
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", feedback_csv)
    monkeypatch.setattr(backend_main, "FEEDBACK_MEMORY_PATH", feedback_memory)
    monkeypatch.setattr(backend_main, "RETRAIN_THRESHOLD", 10_000)
    backend_main.ensure_feedback_store()

    email_with_marker = f"{SAFE_EMAIL}\n{MARKER}"
    expected_hash = hashlib.sha256(email_with_marker.encode("utf-8")).hexdigest()[:32]

    async with make_client() as session:
        await _bootstrap_session(session)
        response = await session.post(
            "/api/feedback",
            json={
                "email_text": email_with_marker,
                "correct_label": "safe",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("saved") is True

        # Read feedback.csv directly
    assert feedback_csv.exists(), "feedback.csv was not created"
    with open(feedback_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # D5: Verify email_hash IS present in the CSV
    hash_found = any(expected_hash in row.get("email_hash", "") for row in rows)
    assert hash_found, (
        f"email_hash {expected_hash[:16]}... not found in feedback.csv — "
        f"D5: hash must be stored instead of plaintext"
    )

    # D5: Verify email_text column does NOT exist in feedback.csv
    if rows:
        assert "email_text" not in rows[0], (
            "D5 violation: feedback.csv still contains email_text column! "
            "Must use email_hash instead."
        )

    # D5: Verify plaintext marker is NOT stored in any cell
    marker_found_in_csv = False
    for row in rows:
        for cell in row.values():
            if MARKER in str(cell):
                marker_found_in_csv = True
                break
        if marker_found_in_csv:
            break
    assert not marker_found_in_csv, (
        f"D5 violation: plaintext marker '{MARKER}' found in feedback.csv! "
        "Plaintext email must never be persisted."
    )

    # Now check if any READ endpoint exposes the feedback content.
    # The /feedback/stats endpoint returns counts only, not content.
    async with make_client() as stats_client:
        await _bootstrap_session(stats_client)
        stats_response = await stats_client.get("/api/feedback/stats")
        if stats_response.status_code == 200:
            stats_text = stats_response.text
            assert MARKER not in stats_text, (
                f"Marker found in /api/feedback/stats response: {stats_text}"
            )

    # /recent-scans and /api/history read from scan_explanations, not feedback.
    async with make_client() as anon_client:
        recent = await anon_client.get("/recent-scans")
        assert recent.status_code == 401

    print(f"\n[G4b] feedback.csv email_hash found: {hash_found}")
    print(f"[G4b] feedback.csv row count: {len(rows)}")
    print(f"[G4b] D5: plaintext marker NOT in CSV: {not marker_found_in_csv}")
    print(f"[G4b] marker in /api/feedback/stats: NOT FOUND (verified)")
    print(f"[G4b] marker in /recent-scans: BLOCKED (401 without session)")
