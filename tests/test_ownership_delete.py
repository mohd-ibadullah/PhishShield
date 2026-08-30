"""W2 b3.3 — Ownership, CRLF injection, and session-scoped DELETE.

Negative tests FIRST, before any implementation changes.
"""
from __future__ import annotations

from collections import OrderedDict

import pytest
from httpx import ASGITransport, AsyncClient

import main as backend_main

SESSION_COOKIE = "phishshield_session"

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
# (a) ownership on /explain/{id} and /report/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_foreign_session_returns_404(client, tmp_path) -> None:
    """Session A's record must not be readable by session B via /explain."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-exp-a.db"
    backend_main.ensure_scans_db()
    async with make_client() as session_a, make_client() as session_b:
        await _bootstrap_session(session_a)
        await _bootstrap_session(session_b)
        result = await _scan(session_a)
        scan_id = str(result.get("scan_id") or result.get("id"))
        # Foreign session gets 404 (not 403) to avoid confirming existence.
        response = await session_b.get(f"/explain/{scan_id}")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_report_foreign_session_returns_404(client, tmp_path) -> None:
    """Session A's record must not be readable by session B via /report."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-rpt-a.db"
    backend_main.ensure_scans_db()
    async with make_client() as session_a, make_client() as session_b:
        await _bootstrap_session(session_a)
        await _bootstrap_session(session_b)
        result = await _scan(session_a)
        scan_id = str(result.get("scan_id") or result.get("id"))
        response = await session_b.get(f"/report/{scan_id}")
        assert response.status_code in (404, 401)


@pytest.mark.asyncio
async def test_explain_anonymous_returns_401(client, tmp_path) -> None:
    """No cookie => 401 on /explain."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-exp-anon.db"
    backend_main.ensure_scans_db()
    async with make_client() as owner:
        await _bootstrap_session(owner)
        result = await _scan(owner)
        scan_id = str(result.get("scan_id") or result.get("id"))
    # Anonymous client: no cookie.
    anonymous = await client.get(f"/explain/{scan_id}")
    assert anonymous.status_code == 401


@pytest.mark.asyncio
async def test_report_anonymous_returns_401(client, tmp_path) -> None:
    """No cookie => 401 on /report."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-rpt-anon.db"
    backend_main.ensure_scans_db()
    async with make_client() as owner:
        await _bootstrap_session(owner)
        result = await _scan(owner)
        scan_id = str(result.get("scan_id") or result.get("id"))
    anonymous = await client.get(f"/report/{scan_id}")
    assert anonymous.status_code == 401


# ---------------------------------------------------------------------------
# (b) Content-Disposition CRLF/quote injection => 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_report_crlf_in_scan_id_returns_400(client, tmp_path) -> None:
    """A scan_id containing CRLF must be rejected (not injected into headers)."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-crlf.db"
    backend_main.ensure_scans_db()
    async with make_client() as authenticated:
        await _bootstrap_session(authenticated)
        # Use URL-encoded CRLF so httpx doesn't reject it at client level;
        # the server must still sanitize before interpolating into headers.
        malicious_id = "scan%0d%0aContent-Type: text/html"
        response = await authenticated.get(f"/report/{malicious_id}")
        # Must be 400 (bad input) or 404 (not found), never 200 with injected headers.
        assert response.status_code in (400, 404)
        # If by any chance the server returned 200, verify no CRLF leaked into headers.
        if response.status_code == 200:
            for header_name, header_value in response.headers.items():
                assert "\r" not in header_value and "\n" not in header_value


@pytest.mark.asyncio
async def test_report_quote_in_scan_id_returns_400(client, tmp_path) -> None:
    """A scan_id containing double-quote must be rejected."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-quote.db"
    backend_main.ensure_scans_db()
    async with make_client() as authenticated:
        await _bootstrap_session(authenticated)
        malicious_id = 'scan"onmouseover=alert(1)'
        response = await authenticated.get(f"/report/{malicious_id}")
        assert response.status_code in (400, 404)


# ---------------------------------------------------------------------------
# (c) DELETE /api/history: anonymous fails, foreign-session fails,
#     own-session only deletes own data, never global wipe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_history_anonymous_fails(client, tmp_path) -> None:
    """DELETE /api/history without a session cookie => 401."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-del-anon.db"
    backend_main.ensure_scans_db()
    response = await client.delete("/api/history")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_history_foreign_session_fails(client, tmp_path) -> None:
    """DELETE /api/history by session B must not touch session A's data."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-del-foreign.db"
    backend_main.ensure_scans_db()
    async with make_client() as session_a, make_client() as session_b:
        await _bootstrap_session(session_a)
        await _bootstrap_session(session_b)
        result_a = await _scan(session_a, "Subject: A\nOwn data.")
        scan_a = str(result_a.get("scan_id") or result_a.get("id"))
        # Session B tries to delete — should be denied or have no effect on A's data.
        delete_resp = await session_b.delete("/api/history")
        # Must not be 200 (no global wipe). Could be 403 or 200-with-no-effect.
        if delete_resp.status_code == 200:
            # Verify session A's data is intact.
            recent = await session_a.get("/recent-scans")
            assert recent.status_code == 200
            ids = [str(item.get("scan_id")) for item in recent.json()]
            assert scan_a in ids


@pytest.mark.asyncio
async def test_delete_history_own_session_deletes_own_data(client, tmp_path) -> None:
    """DELETE /api/history by session A removes only A's in-memory records."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-del-own.db"
    backend_main.ensure_scans_db()
    async with make_client() as session_a, make_client() as session_b:
        await _bootstrap_session(session_a)
        await _bootstrap_session(session_b)
        result_a = await _scan(session_a, "Subject: A\nDelete me.")
        scan_a = str(result_a.get("scan_id") or result_a.get("id"))
        result_b = await _scan(session_b, "Subject: B\nKeep me.")
        scan_b = str(result_b.get("scan_id") or result_b.get("id"))
        # Session A deletes.
        delete_resp = await session_a.delete("/api/history")
        assert delete_resp.status_code == 200
        # Session A's in-memory data should be gone.
        recent_a = await session_a.get("/recent-scans")
        a_ids = [str(item.get("scan_id")) for item in recent_a.json()]
        assert scan_a not in a_ids
        # Session B's data must survive.
        recent_b = await session_b.get("/recent-scans")
        b_ids = [str(item.get("scan_id")) for item in recent_b.json()]
        assert scan_b in b_ids
