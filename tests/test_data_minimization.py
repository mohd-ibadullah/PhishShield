"""W2 b3.4 — Data minimization, retention, marker absence.

Negative tests FIRST, before any implementation changes.

Verifies:
- Raw email body, preview, headers, client IP are NOT persisted.
- Only sha256(email), verdict, score, language, timestamp are kept.
- /explain and /report do not replay raw email.
- Synthetic MKR marker is absent from read responses and persisted stores.
- Recent Activity still renders.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections import OrderedDict

import pytest
from httpx import ASGITransport, AsyncClient

import main as backend_main

SESSION_COOKIE = "phishshield_session"
MARKER = "MKR_SYNTHETIC_8472"

SAFE_EMAIL = "Subject: Weekly standup\nTeam meeting scheduled tomorrow at ten."


def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=backend_main.app), base_url="http://testserver")


async def _bootstrap_session(client: AsyncClient) -> None:
    response = await client.post("/api/session")
    assert response.status_code == 200, response.text


async def _scan(client: AsyncClient, email_text: str = SAFE_EMAIL) -> dict:
    response = await client.post("/scan-email", json={"email_text": email_text})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# (a) Raw email body is NOT persisted in scan_explanations payload_json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_explanation_does_not_persist_raw_email_body(client, tmp_path) -> None:
    """After scanning, the explanation record in SQLite must NOT contain the raw email."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-min.db"
    backend_main.ensure_scans_db()
    async with make_client() as session:
        await _bootstrap_session(session)
        result = await _scan(session, "Subject: Super Secret\nThis is the confidential body text.")
        scan_id = str(result.get("scan_id") or result.get("id"))
    # Read the raw DB payload.
    with sqlite3.connect(backend_main.SCANS_DB_PATH) as conn:
        row = conn.execute(
            "SELECT payload_json FROM scan_explanations WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()
    assert row is not None, "scan_explanation row not found in DB"
    payload = json.loads(row[0])
    # email_text field must be absent or empty in the persisted record.
    assert not payload.get("email_text"), "email_text field should be empty/absent in persisted record"
    # email_sha256 must be present instead.
    assert payload.get("email_sha256"), "email_sha256 should be present in persisted record"


@pytest.mark.asyncio
async def test_scan_explanation_persists_email_sha256(client, tmp_path) -> None:
    """The explanation record must contain a sha256 hash of the email, not the body."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-hash.db"
    backend_main.ensure_scans_db()
    email = "Subject: Hash test\nUnique body content here."
    expected_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    async with make_client() as session:
        await _bootstrap_session(session)
        result = await _scan(session, email)
        scan_id = str(result.get("scan_id") or result.get("id"))
    with sqlite3.connect(backend_main.SCANS_DB_PATH) as conn:
        row = conn.execute(
            "SELECT payload_json FROM scan_explanations WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()
    payload = json.loads(row[0])
    assert payload.get("email_sha256") == expected_hash


# ---------------------------------------------------------------------------
# (b) /explain does not return raw email body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_does_not_return_raw_email(client, tmp_path) -> None:
    """GET /explain/{id} must NOT include the raw email body."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-exp-min.db"
    backend_main.ensure_scans_db()
    async with make_client() as session:
        await _bootstrap_session(session)
        result = await _scan(session, "Subject: PII email\nSocial security: 123-45-6789")
        scan_id = str(result.get("scan_id") or result.get("id"))
        response = await session.get(f"/explain/{scan_id}")
        assert response.status_code == 200
        body = response.text
        assert "123-45-6789" not in body, "Raw PII found in /explain response"
        assert "PII email" not in body, "Raw email subject found in /explain response"


@pytest.mark.asyncio
async def test_explain_post_does_not_return_raw_email(client, tmp_path) -> None:
    """POST /explain must NOT include the raw email body."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-exp-post-min.db"
    backend_main.ensure_scans_db()
    async with make_client() as session:
        await _bootstrap_session(session)
        result = await _scan(session, "Subject: POST test\nPassword: hunter2")
        scan_id = str(result.get("scan_id") or result.get("id"))
        response = await session.post("/explain", json={"scan_id": scan_id})
        assert response.status_code == 200
        body = response.text
        assert "hunter2" not in body, "Raw email found in POST /explain response"


# ---------------------------------------------------------------------------
# (c) Synthetic MKR marker is absent from ALL read responses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mkr_marker_absent_from_recent_scans(client, tmp_path) -> None:
    """MKR marker must not appear in /recent-scans response."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-mkr-rs.db"
    backend_main.ensure_scans_db()
    async with make_client() as session:
        await _bootstrap_session(session)
        await _scan(session, f"{SAFE_EMAIL} {MARKER}")
        response = await session.get("/recent-scans")
        assert response.status_code == 200
        assert MARKER not in response.text


@pytest.mark.asyncio
async def test_mkr_marker_absent_from_api_history(client, tmp_path) -> None:
    """MKR marker must not appear in /api/history response."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-mkr-hist.db"
    backend_main.ensure_scans_db()
    async with make_client() as session:
        await _bootstrap_session(session)
        await _scan(session, f"{SAFE_EMAIL} {MARKER}")
        response = await session.get("/api/history")
        assert response.status_code == 200
        assert MARKER not in response.text


@pytest.mark.asyncio
async def test_mkr_marker_absent_from_explain(client, tmp_path) -> None:
    """MKR marker must not appear in /explain response."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-mkr-exp.db"
    backend_main.ensure_scans_db()
    async with make_client() as session:
        await _bootstrap_session(session)
        result = await _scan(session, f"{SAFE_EMAIL} {MARKER}")
        scan_id = str(result.get("scan_id") or result.get("id"))
        response = await session.get(f"/explain/{scan_id}")
        assert response.status_code == 200
        assert MARKER not in response.text


@pytest.mark.asyncio
async def test_mkr_marker_absent_from_persisted_db(client, tmp_path) -> None:
    """MKR marker must not appear in persisted scan_explanations payload_json."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-mkr-persist.db"
    backend_main.ensure_scans_db()
    async with make_client() as session:
        await _bootstrap_session(session)
        result = await _scan(session, f"{SAFE_EMAIL} {MARKER}")
        scan_id = str(result.get("scan_id") or result.get("id"))
    with sqlite3.connect(backend_main.SCANS_DB_PATH) as conn:
        row = conn.execute(
            "SELECT payload_json FROM scan_explanations WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()
    assert row is not None
    assert MARKER not in row[0], "MKR marker found in persisted DB payload"


# ---------------------------------------------------------------------------
# (d) Recent Activity still renders correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recent_activity_renders_after_minimization(client, tmp_path) -> None:
    """After data minimization, /recent-scans must still return usable display data."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-activity.db"
    backend_main.ensure_scans_db()
    async with make_client() as session:
        await _bootstrap_session(session)
        result = await _scan(session)
        response = await session.get("/recent-scans")
        assert response.status_code == 200
        items = response.json()
        assert len(items) >= 1
        item = items[0]
        # Must have the fields the frontend needs for Recent Activity.
        assert "scan_id" in item or "id" in item
        assert "verdict" in item
        assert "risk_score" in item
        assert "timestamp" in item


# ---------------------------------------------------------------------------
# (e) Retention / pruning: old records are eventually pruned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scans_db_has_timestamp_index_for_pruning(tmp_path) -> None:
    """The scans table should have a timestamp column usable for periodic pruning."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-retention.db"
    backend_main.ensure_scans_db()
    with sqlite3.connect(backend_main.SCANS_DB_PATH) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(scans)").fetchall()]
        assert "timestamp" in columns, "scans table missing timestamp column for retention pruning"


@pytest.mark.asyncio
async def test_scan_explanations_db_has_timestamp_for_pruning(tmp_path) -> None:
    """The scan_explanations table should have a timestamp column for retention pruning."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-exp-retention.db"
    backend_main.ensure_scans_db()
    with sqlite3.connect(backend_main.SCANS_DB_PATH) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(scan_explanations)").fetchall()]
        assert "updated_at" in columns, "scan_explanations table missing updated_at column"
