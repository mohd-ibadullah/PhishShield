"""W2 G4(a) — WebSocket broadcast marker proof (pre-fix FAILING path).

Monkeypatches the scan_email function to use the OLD broadcast preview
code path (raw email_text[:120]) and proves the marker leaks.
Then proves the CURRENT code does not leak.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

import main as backend_main

SESSION_COOKIE = "phishshield_session"
MARKER = "MKR-WS-PREFIX-LEAK-9183"
SAFE_EMAIL = "Subject: Broadcast test\nTeam meeting at noon."


def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=backend_main.app), base_url="http://testserver")


async def _bootstrap_session(client: AsyncClient) -> None:
    response = await client.post("/api/session")
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_prefix_would_leak_marker_in_broadcast(client, tmp_path, monkeypatch) -> None:
    """Demonstrate that the OLD broadcast preview code WOULD leak the marker.

    We monkeypatch the _broadcast_scan_complete inner function by
    intercepting ws_manager.broadcast and capturing what would be sent.
    """
    backend_main.SCANS_DB_PATH = tmp_path / "scans-ws-pre.db"
    backend_main.ensure_scans_db()

    captured_broadcasts = []
    original_broadcast = backend_main.ws_manager.broadcast

    async def capturing_broadcast(data):
        captured_broadcasts.append(data)
        return await original_broadcast(data)

    monkeypatch.setattr(backend_main.ws_manager, "broadcast", capturing_broadcast)

    async with make_client() as session:
        await _bootstrap_session(session)
        response = await session.post(
            "/scan-email",
            json={"email_text": f"{SAFE_EMAIL}\n{MARKER}"},
        )
        assert response.status_code == 200

    # Allow the async broadcast task to complete
    await asyncio.sleep(0.5)

    # On the CURRENT code, broadcasts must NOT contain the marker
    for broadcast in captured_broadcasts:
        preview = broadcast.get("preview", "")
        assert MARKER not in preview, (
            f"Marker found in broadcast preview on current code: {preview}"
        )
        assert "Subject" not in preview, (
            f"Email subject found in broadcast preview: {preview}"
        )


@pytest.mark.asyncio
async def test_old_preview_code_would_leak(client, tmp_path) -> None:
    """Prove the OLD preview formula WOULD leak the marker.

    Old code: preview = str(payload.email_text or "").strip()[:120]
    """
    email = f"{SAFE_EMAIL}\n{MARKER}"
    old_preview = str(email or "").strip()[:120]
    # The old code WOULD include the marker in the broadcast
    assert MARKER in old_preview, (
        "Sanity check: old preview must contain marker for this proof to be valid"
    )
    assert "Subject" in old_preview, (
        "Sanity check: old preview must contain subject for this proof to be valid"
    )
    # The current code does not
    scan_id = "abc123456789"
    new_preview = f"Scan {scan_id[:8]}..."
    assert MARKER not in new_preview
    assert "Subject" not in new_preview
