"""D1 — /feedback/stats semantics fix.

Pre-fix failures:
- zero feedback → model_improving must be False
- needed_for_retrain must be > 0 when total_feedback == 0
- total_feedback and pending_retrain must be consistent
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

import main as backend_main

SAFE_EMAIL = "Subject: Stats test\nTeam meeting at noon."


def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=backend_main.app), base_url="http://testserver")


async def _bootstrap_session(client: AsyncClient) -> None:
    response = await client.post("/api/session")
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_zero_feedback_model_improving_is_false(client, tmp_path, monkeypatch) -> None:
    """PRE-FIX FAILURE: with zero feedback, model_improving must be False."""
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", tmp_path / "feedback.csv")
    monkeypatch.setattr(backend_main, "FEEDBACK_MEMORY_PATH", tmp_path / "feedback_memory.json")
    monkeypatch.setattr(backend_main, "FEEDBACK_STATE_PATH", tmp_path / "feedback_state.json")
    monkeypatch.setattr(backend_main, "RETRAIN_THRESHOLD", 50)
    backend_main.ensure_feedback_store()

    async with make_client() as session:
        await _bootstrap_session(session)
        response = await session.get("/api/feedback/stats")
        assert response.status_code == 200
        body = response.json()
        # PRE-FIX: this fails because model_improving defaults to True
        assert body.get("model_improving") is False, (
            f"model_improving should be False with zero feedback, got {body.get('model_improving')}"
        )


@pytest.mark.asyncio
async def test_zero_feedback_needed_for_retrain_positive(client, tmp_path, monkeypatch) -> None:
    """PRE-FIX FAILURE: with zero feedback, needed_for_retrain must be > 0."""
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", tmp_path / "feedback.csv")
    monkeypatch.setattr(backend_main, "FEEDBACK_MEMORY_PATH", tmp_path / "feedback_memory.json")
    monkeypatch.setattr(backend_main, "FEEDBACK_STATE_PATH", tmp_path / "feedback_state.json")
    monkeypatch.setattr(backend_main, "RETRAIN_THRESHOLD", 50)
    backend_main.ensure_feedback_store()

    async with make_client() as session:
        await _bootstrap_session(session)
        response = await session.get("/api/feedback/stats")
        assert response.status_code == 200
        body = response.json()
        # PRE-FIX: this fails because needed_for_retrain is 0 when pending is also 0
        # but total_feedback is 0 too, meaning nothing has been collected
        needed = body.get("needed_for_retrain", 0)
        threshold = 50
        assert needed > 0, (
            f"needed_for_retrain should be > 0 with 0 feedback and threshold {threshold}, got {needed}"
        )


@pytest.mark.asyncio
async def test_counts_consistent_under_synthetic_rows(client, tmp_path, monkeypatch) -> None:
    """PRE-FIX FAILURE: total_feedback and pending_retrain may diverge."""
    feedback_csv = tmp_path / "feedback.csv"
    feedback_memory = tmp_path / "feedback_memory.json"
    feedback_state = tmp_path / "feedback_state.json"
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", feedback_csv)
    monkeypatch.setattr(backend_main, "FEEDBACK_MEMORY_PATH", feedback_memory)
    monkeypatch.setattr(backend_main, "FEEDBACK_STATE_PATH", feedback_state)
    monkeypatch.setattr(backend_main, "RETRAIN_THRESHOLD", 10_000)
    backend_main.ensure_feedback_store()

    # Write 5 synthetic rows directly to CSV
    import csv
    with open(feedback_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(backend_main.FEEDBACK_COLUMNS)
        for i in range(5):
            writer.writerow([f"email {i}", "safe", "Suspicious", "2026-08-30", f"scan-{i}"])

    async with make_client() as session:
        await _bootstrap_session(session)
        response = await session.get("/api/feedback/stats")
        assert response.status_code == 200
        body = response.json()
        # total_feedback comes from in-memory entries (0 after fresh start)
        # pending_retrain comes from CSV row count (5)
        # These should be consistent or explicitly documented as different sources
        total = body.get("total_feedback", 0)
        pending = body.get("pending_retrain", 0)
        # The CSV has 5 rows but total_feedback may show 0 (in-memory is empty)
        # This inconsistency is the defect
        if total == 0 and pending > 0:
            pytest.fail(
                f"INCONSISTENCY: total_feedback={total} but pending_retrain={pending}. "
                f"CSV has 5 rows but in-memory entries are empty."
            )
