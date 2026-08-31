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


def test_ws_broadcast_receives_scan_result():
    """WebSocket broadcast contains scan_id, verdict, risk_score.
    Privacy regression guard: broadcast must never leak email content.
    Uses starlette TestClient (sync) which supports websocket_connect."""
    import json
    from starlette.testclient import TestClient
    import main as backend_main

    with TestClient(backend_main.app) as tc:
        # Establish session
        session_resp = tc.post("/api/session")
        assert session_resp.status_code == 200

        # Connect to WebSocket
        with tc.websocket_connect("/ws/feed") as ws:
            # Drain pending messages from prior tests until connected
            connected = None
            for _ in range(10):
                msg = ws.receive_json()
                if msg.get("type") == "connected":
                    connected = msg
                    break
            assert connected is not None, (
                f"Expected 'connected' message but got: {msg}"
            )

            # Trigger scan
            scan_resp = tc.post(
                "/scan-email",
                json={
                    "email_text": "Subject: Verify Account' + chr(92) + 'n' + chr(92) + 'nClick: http://suspicious-bank.tk",
                },
            )
            assert scan_resp.status_code == 200
            scan_data = scan_resp.json()
            scan_id = scan_data["scan_id"]

            # Receive broadcast
            broadcast = ws.receive_json()
            assert broadcast["type"] == "scan_complete"
            assert broadcast["scan_id"] == scan_id
            assert "verdict" in broadcast
            assert "risk_score" in broadcast

            # Privacy: raw email content must NOT appear in broadcast
            broadcast_str = json.dumps(broadcast)
            assert "suspicious-bank.tk" not in broadcast_str, (
                "Privacy violation: raw URL leaked in broadcast"
            )
            assert "Verify Account" not in broadcast_str, (
                "Privacy violation: raw subject leaked in broadcast"
            )
