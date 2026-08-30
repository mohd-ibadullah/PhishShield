"""Basic HTTP / input safety checks (no crash, no path tricks)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _bootstrap_session(client) -> None:
    bootstrap = await client.post("/api/session")
    assert bootstrap.status_code == 200


async def test_scan_email_rejects_invalid_json(client) -> None:
    response = await client.post(
        "/scan-email",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


async def test_explain_unknown_scan_id_is_404(client) -> None:
    # Anonymous callers are denied first (b3.2 session identity).
    anonymous = await client.get("/explain/no-such-scan-id-xxxxxxxx")
    assert anonymous.status_code == 401
    await _bootstrap_session(client)
    response = await client.get("/explain/no-such-scan-id-xxxxxxxx")
    assert response.status_code == 404


async def test_report_unknown_scan_id_is_404(client) -> None:
    anonymous = await client.get("/report/no-such-scan-id-xxxxxxxx")
    assert anonymous.status_code == 401
    await _bootstrap_session(client)
    response = await client.get("/report/no-such-scan-id-xxxxxxxx")
    assert response.status_code == 404


async def test_explain_scan_id_not_path_traversal(client) -> None:
    """Route param is opaque; traversal-like segments must not leak files."""
    await _bootstrap_session(client)
    rid = "..%2f..%2fetc%2fpasswd"
    response = await client.get(f"/explain/{rid}")
    assert response.status_code == 404
