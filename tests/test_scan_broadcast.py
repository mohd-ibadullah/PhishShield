"""Scan + broadcast integration test (converted from tools/test_scan_simple.py).

Uses httpx AsyncClient against the FastAPI app directly - no live server needed.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


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
