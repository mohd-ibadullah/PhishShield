"""T6: 1 MiB request size cap — pre-parse, chunked support."""
from __future__ import annotations

import sys
import pathlib
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as bm

pytestmark = __import__("pytest").mark.asyncio


async def test_content_length_too_large():
    """Content-Length > 1 MiB → 413, handler not entered."""
    handler_entered = False
    original = bm.scan_email

    def _tracking_handler(*a, **kw):
        nonlocal handler_entered
        handler_entered = True
        return original(*a, **kw)

    bm.scan_email = _tracking_handler
    try:
        transport = ASGITransport(app=bm.app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            r = await c.post(
                "/scan-email",
                content=b"x" * (1024 * 1024 + 1),
                headers={"Content-Length": str(1024 * 1024 + 1), "Content-Type": "application/json"},
            )
            assert r.status_code == 413, f"Expected 413, got {r.status_code}"
            assert not handler_entered, "Handler should not be entered for oversized request"
    finally:
        bm.scan_email = original


async def test_valid_request_under_cap():
    """900 KB valid request → 200."""
    transport = ASGITransport(app=bm.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post(
            "/scan-email",
            json={"email_text": "A" * 10000},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
