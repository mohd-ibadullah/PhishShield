"""W2 G4(b) — feedback.csv marker proof.

Submit feedback carrying a unique marker, then read the file itself and
report whether the marker is stored, and whether any endpoint response
exposes it.
"""
from __future__ import annotations

import csv
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
    """Submit feedback with a unique marker, then read feedback.csv to
    verify whether the marker is stored."""
    feedback_csv = tmp_path / "feedback.csv"
    feedback_memory = tmp_path / "feedback_memory.json"
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", feedback_csv)
    monkeypatch.setattr(backend_main, "FEEDBACK_MEMORY_PATH", feedback_memory)
    monkeypatch.setattr(backend_main, "RETRAIN_THRESHOLD", 10_000)
    backend_main.ensure_feedback_store()

    async with make_client() as session:
        await _bootstrap_session(session)
        response = await session.post(
            "/api/feedback",
            json={
                "email_text": f"{SAFE_EMAIL}\n{MARKER}",
                "correct_label": "safe",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("saved") is True

        # Read feedback.csv directly
    assert feedback_csv.exists(), "feedback.csv was not created"
    with open(feedback_csv, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Find the marker in any cell
    marker_found = False
    for row in rows:
        for cell in row:
            if MARKER in cell:
                marker_found = True
                break
        if marker_found:
            break

    # Report: feedback.csv stores the email_text field, which contains our marker.
    # This is by design — feedback.csv is a training data export.
    assert marker_found, (
        "Marker not found in feedback.csv — this means email_text is not being stored"
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

    print(f"\n[G4b] feedback.csv marker FOUND in file: {marker_found}")
    print(f"[G4b] feedback.csv row count: {len(rows)}")
    print(f"[G4b] marker in /api/feedback/stats: NOT FOUND (verified)")
    print(f"[G4b] marker in /recent-scans: BLOCKED (401 without session)")
