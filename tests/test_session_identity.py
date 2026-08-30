"""Server-issued session identity contract (W2 / b3.2).

Sessions are cryptographically random, server-issued, HttpOnly-cookie
tokens. The server stores only a SHA-256 hash of the token. All read
operations derive caller identity exclusively from the server-issued
cookie; client-supplied session_id values are never authentication.
"""
from __future__ import annotations

from collections import OrderedDict

import pytest
from httpx import ASGITransport, AsyncClient

import main as backend_main

SESSION_COOKIE = "phishshield_session"

SAFE_EMAIL_A = "Subject: Weekly standup\nTeam meeting scheduled tomorrow at ten. No action required."
SAFE_EMAIL_B = "Subject: Sprint retro\nRetro notes are in the shared doc. Nothing else needed."
ATTACKER_SESSION = "attacker-chosen-session-id"


def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=backend_main.app), base_url="http://testserver")


async def _bootstrap_session(client: AsyncClient) -> None:
    response = await client.post("/api/session")
    assert response.status_code == 200, response.text


async def _scan(client: AsyncClient, email_text: str, **extra) -> dict:
    response = await client.post("/scan-email", json={"email_text": email_text, **extra})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# (b) no cookie -> 401 on every read endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recent_scans_requires_session_cookie(client, tmp_path) -> None:
    backend_main.SCANS_DB_PATH = tmp_path / "scans-b1.db"
    backend_main.ensure_scans_db()
    response = await client.get("/recent-scans")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_history_requires_session_cookie(client, tmp_path) -> None:
    backend_main.SCANS_DB_PATH = tmp_path / "scans-b2.db"
    backend_main.ensure_scans_db()
    response = await client.get("/api/history")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_explain_and_report_require_session_cookie(client, tmp_path) -> None:
    backend_main.SCANS_DB_PATH = tmp_path / "scans-b3.db"
    backend_main.ensure_scans_db()
    # Create a record with an authenticated session first.
    async with make_client() as owner:
        await _bootstrap_session(owner)
        result = await _scan(owner, SAFE_EMAIL_A)
        scan_id = str(result.get("scan_id") or result.get("id"))
    # A client with NO cookie gets 401 (not 404) even though the id exists.
    anonymous = await client.get(f"/explain/{scan_id}")
    assert anonymous.status_code == 401
    anonymous_report = await client.get(f"/report/{scan_id}")
    assert anonymous_report.status_code == 401


# ---------------------------------------------------------------------------
# (a) session A cannot read session B
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_a_cannot_read_session_b_records(client, tmp_path) -> None:
    backend_main.SCANS_DB_PATH = tmp_path / "scans-a.db"
    backend_main.ensure_scans_db()
    async with make_client() as session_a, make_client() as session_b:
        await _bootstrap_session(session_a)
        await _bootstrap_session(session_b)
        result_b = await _scan(session_b, SAFE_EMAIL_B)
        scan_b = str(result_b.get("scan_id") or result_b.get("id"))

        # Per-record reads from the wrong session are denied.
        explain = await session_a.get(f"/explain/{scan_b}")
        assert explain.status_code in (401, 403, 404)
        report = await session_a.get(f"/report/{scan_b}")
        assert report.status_code in (401, 403, 404)

        # List endpoints never include the other session's rows.
        recent = await session_a.get("/recent-scans")
        assert recent.status_code == 200
        assert scan_b not in [str(item.get("scan_id")) for item in recent.json()]
        history = await session_a.get("/api/history")
        assert history.status_code == 200
        assert scan_b not in [str(item.get("id")) for item in history.json()]


# ---------------------------------------------------------------------------
# (c) client cannot self-assign a session_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_client_cannot_self_assign_session_id(client, tmp_path) -> None:
    backend_main.SCANS_DB_PATH = tmp_path / "scans-c.db"
    backend_main.ensure_scans_db()
    response = await client.post(
        "/scan-email",
        json={"email_text": SAFE_EMAIL_A, "session_id": ATTACKER_SESSION},
    )
    assert response.status_code == 200
    # The server must issue its own HttpOnly cookie, not honor the body value.
    set_cookie = response.headers.get("set-cookie", "")
    assert SESSION_COOKIE in set_cookie
    assert "httponly" in set_cookie.lower()
    # The server-issued token must not echo the client-chosen value.
    cookie_value = set_cookie.split(SESSION_COOKIE + "=", 1)[1].split(";", 1)[0]
    assert cookie_value != ATTACKER_SESSION

    # The client-chosen id grants nothing later: a fresh anonymous client
    # cannot use it as a query parameter to read data.
    scan_id = str(response.json().get("scan_id") or response.json().get("id"))
    async with make_client() as anonymous:
        recent = await anonymous.get("/recent-scans", params={"session_id": ATTACKER_SESSION})
        assert recent.status_code == 401
        history = await anonymous.get("/api/history", params={"session_id": ATTACKER_SESSION})
        assert history.status_code == 401
        explain = await anonymous.get(f"/explain/{scan_id}")
        assert explain.status_code == 401
    # Even the submitting client's own reads key off the server cookie, and the
    # query parameter is ignored entirely.
    recent = await client.get("/recent-scans", params={"session_id": ATTACKER_SESSION})
    assert recent.status_code == 200
    assert scan_id in [str(item.get("scan_id")) for item in recent.json()]


# ---------------------------------------------------------------------------
# (d) /api/feedback uses authenticated session + rate limit + per-session cap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feedback_denied_without_session_even_with_internal_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", tmp_path / "feedback.csv")
    monkeypatch.setattr(backend_main, "FEEDBACK_MEMORY_PATH", tmp_path / "feedback_memory.json")
    backend_main.ensure_feedback_store()
    async with make_client() as anonymous:
        response = await anonymous.post(
            "/api/feedback",
            json={"email_text": SAFE_EMAIL_A, "correct_label": "safe"},
            headers={"x-internal-api-key": "test-internal-key"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_feedback_allowed_with_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", tmp_path / "feedback.csv")
    monkeypatch.setattr(backend_main, "FEEDBACK_MEMORY_PATH", tmp_path / "feedback_memory.json")
    backend_main.ensure_feedback_store()
    async with make_client() as authenticated:
        await _bootstrap_session(authenticated)
        response = await authenticated.post(
            "/api/feedback",
            json={"email_text": SAFE_EMAIL_A, "correct_label": "phishing"},
        )
        assert response.status_code == 200, response.text
        assert response.json().get("saved") is True


@pytest.mark.asyncio
async def test_feedback_rate_limited_per_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", tmp_path / "feedback.csv")
    monkeypatch.setattr(backend_main, "FEEDBACK_MEMORY_PATH", tmp_path / "feedback_memory.json")
    monkeypatch.setattr(backend_main, "RETRAIN_THRESHOLD", 10_000)
    backend_main.ensure_feedback_store()
    async with make_client() as authenticated:
        await _bootstrap_session(authenticated)
        statuses = []
        for index in range(11):
            response = await authenticated.post(
                "/api/feedback",
                json={"email_text": f"{SAFE_EMAIL_A} variant {index}", "correct_label": "safe"},
            )
            statuses.append(response.status_code)
    assert statuses[-1] == 429
    assert all(status == 200 for status in statuses[:-1])


@pytest.mark.asyncio
async def test_feedback_per_session_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", tmp_path / "feedback.csv")
    monkeypatch.setattr(backend_main, "FEEDBACK_MEMORY_PATH", tmp_path / "feedback_memory.json")
    monkeypatch.setattr(backend_main, "RETRAIN_THRESHOLD", 10_000)
    monkeypatch.setattr(backend_main, "FEEDBACK_SESSION_CAP", 2)
    monkeypatch.setattr(backend_main, "FEEDBACK_RATE_LIMIT_MAX", 100)
    backend_main.ensure_feedback_store()
    async with make_client() as authenticated:
        await _bootstrap_session(authenticated)
        for index in range(2):
            response = await authenticated.post(
                "/api/feedback",
                json={"email_text": f"{SAFE_EMAIL_B} cap {index}", "correct_label": "safe"},
            )
            assert response.status_code == 200
        capped = await authenticated.post(
            "/api/feedback",
            json={"email_text": f"{SAFE_EMAIL_B} cap over", "correct_label": "safe"},
        )
        assert capped.status_code == 429
        assert "cap" in str(capped.json().get("detail", "")).lower()


# ---------------------------------------------------------------------------
# cookie issuance contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_bootstrap_issues_httponly_cookie(client) -> None:
    response = await client.post("/api/session")
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert SESSION_COOKIE in set_cookie
    assert "httponly" in set_cookie.lower()
    # Only a hash is ever stored server-side.
    cookie_value = set_cookie.split(SESSION_COOKIE + "=", 1)[1].split(";", 1)[0]
    token_hash = backend_main.hash_session_token(cookie_value)
    session_records = backend_main.session_records_snapshot()
    assert token_hash in session_records
    assert cookie_value not in str(session_records)
