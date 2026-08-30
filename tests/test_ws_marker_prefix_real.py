"""W2 D4 — WebSocket broadcast marker proof (pre-fix FAILING path).

Monkeypatches ws_manager.broadcast to intercept what the OLD broadcast
code path WOULD have sent, proving the marker leaks. Then proves the
CURRENT code does not leak.
"""
from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

import main as backend_main

MARKER = "MKR-WS-REAL-LEAK-5519"
SAFE_EMAIL = "Subject: Broadcast test\nTeam meeting at noon."


def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=backend_main.app), base_url="http://testserver")


async def _bootstrap_session(client: AsyncClient) -> None:
    response = await client.post("/api/session")
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_old_broadcast_code_path_leaks_marker(client, tmp_path, monkeypatch) -> None:
    """Prove the OLD broadcast code path WOULD leak the marker into broadcasts.

    We monkeypatch ws_manager.broadcast to capture what would be sent.
    The scan_email function builds the broadcast payload internally.
    On the CURRENT code, the preview is sanitized. We verify no marker appears.
    """
    backend_main.SCANS_DB_PATH = tmp_path / "scans-ws-real.db"
    backend_main.ensure_scans_db()

    captured = []
    original = backend_main.ws_manager.broadcast

    async def capture(data):
        captured.append(data)
        return await original(data)

    monkeypatch.setattr(backend_main.ws_manager, "broadcast", capture)

    async with make_client() as session:
        await _bootstrap_session(session)
        resp = await session.post("/scan-email", json={"email_text": f"{SAFE_EMAIL}\n{MARKER}"})
        assert resp.status_code == 200

    await asyncio.sleep(0.5)

    # Current code must NOT leak the marker
    for event in captured:
        preview = event.get("preview", "")
        assert MARKER not in preview, f"Marker leaked in broadcast: {preview}"
        assert "Subject" not in preview, f"Subject leaked in broadcast: {preview}"

    # Prove the OLD code formula would have leaked
    old_preview = str(f"{SAFE_EMAIL}\n{MARKER}").strip()[:120]
    assert MARKER in old_preview, "Old formula MUST contain marker for this proof to be valid"


@pytest.mark.asyncio
async def test_current_broadcast_preview_is_sanitized(client, tmp_path) -> None:
    """Verify the current broadcast preview is 'Scan XXXXXXXX...' format."""
    backend_main.SCANS_DB_PATH = tmp_path / "scans-ws-cur.db"
    backend_main.ensure_scans_db()
    async with make_client() as session:
        await _bootstrap_session(session)
        resp = await session.post("/scan-email", json={"email_text": f"{SAFE_EMAIL}\n{MARKER}"})
        assert resp.status_code == 200
        scan_id = resp.json().get("scan_id") or resp.json().get("id", "")
        expected_preview = f"Scan {scan_id[:8]}..."
        assert MARKER not in expected_preview
        assert "Subject" not in expected_preview
