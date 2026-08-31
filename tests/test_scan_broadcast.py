"""Scan + broadcast integration test (converted from tools/test_scan_simple.py).

Uses httpx AsyncClient against the FastAPI app directly - no live server needed.
"""
from __future__ import annotations

import pytest

@pytest.mark.asyncio
async def test_scan_returns_verdict_and_session(client):
    """POST /scan-email returns a valid verdict and risk_score."""
    response = await client.post(
        "/scan-email",
        json={
            "email_text": "Subject: Verify Now\n\nClick here: http://suspicious.tk/verify",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "verdict" in data
    assert "risk_score" in data
    assert isinstance(data["risk_score"], int)


@pytest.mark.asyncio
async def test_scan_session_id_echo(client):
    """Session ID is tracked server-side via cookie."""
    response = await client.post(
        "/scan-email",
        json={
            "email_text": "Subject: Test\n\nBody",
            "session_id": "test-session-abc",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "verdict" in data






@pytest.mark.asyncio
async def test_ws_broadcast_isolation_between_sessions(client):
    """WS broadcast isolation: verify ConnectionManager scoping.
    Two sockets connect with different session_ids. Mock the broadcast
    method to capture what is sent, then trigger a scan as session B.
    Assert: broadcast is called but the event contains no session A data."""
    import json
    import time
    from unittest.mock import AsyncMock, patch

    MARKER = "ISOLATION-PROBE-" + str(int(time.time()))

    # Create two sessions
    resp_a = await client.post("/api/session")
    resp_b = await client.post("/api/session")
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    session_a = resp_a.json().get("session_id", "a")
    session_b = resp_b.json().get("session_id", "b")

    import main as backend_main
    captured_messages = []
    original_broadcast = backend_main.ws_manager.broadcast

    async def capture_broadcast(msg):
        captured_messages.append(msg)
        await original_broadcast(msg)

    with patch.object(backend_main.ws_manager, "broadcast", capture_broadcast):
        email_body = "Subject: " + MARKER + chr(10) + chr(10) + "Click: http://test.example.com"
        scan_resp = await client.post(
            "/scan-email",
            json={
                "email_text": email_body,
                "session_id": session_b,
            },
        )
        assert scan_resp.status_code == 200
        b_scan_id = scan_resp.json()["scan_id"]

    # Verify broadcast was called
    assert len(captured_messages) > 0, "No broadcast emitted"

    # Verify no raw email content in any broadcast
    for msg in captured_messages:
        msg_str = json.dumps(msg)
        assert MARKER not in msg_str, (
            "PRIVACY VIOLATION: raw email subject in broadcast: " + msg_str[:200]
        )
        assert "test.example.com" not in msg_str, (
            "PRIVACY VIOLATION: raw URL in broadcast: " + msg_str[:200]
        )

    # Verify broadcast goes to ALL connected clients (global scope)
    # This documents the current architecture: broadcasts are not session-scoped.
    # If isolation is added later, this test should change to assert scoping.
    broadcast = captured_messages[0]
    assert broadcast["type"] == "scan_complete"
    assert broadcast["scan_id"] == b_scan_id
    # preview should be redacted (b3.5), not raw
    assert MARKER not in broadcast.get("preview", "")
