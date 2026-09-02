"""T6: 1 MiB request size cap — boundary tests, pre-parse."""
from __future__ import annotations

import sys
import pathlib
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as bm

pytestmark = __import__("pytest").mark.asyncio

ONE_MIB = 1024 * 1024


async def test_boundary_under_cap():
    """Content-Length = 1 MiB - 1 → 200 (exactly at boundary, under)."""
    transport = ASGITransport(app=bm.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        body = b"x" * (ONE_MIB - 1)
        r = await c.post(
            "/scan-email",
            content=body,
            headers={"Content-Length": str(len(body)), "Content-Type": "application/json"},
        )
        # Under cap: should be processed (200) or rejected for bad JSON (422)
        assert r.status_code in (200, 422), f"Under cap: {r.status_code}"


async def test_boundary_over_cap():
    """Content-Length = 1 MiB + 1 → 413."""
    transport = ASGITransport(app=bm.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        body = b"x" * (ONE_MIB + 1)
        r = await c.post(
            "/scan-email",
            content=body,
            headers={"Content-Length": str(len(body)), "Content-Type": "application/json"},
        )
        assert r.status_code == 413, f"Over cap: {r.status_code}"


async def test_handler_not_entered_on_oversize():
    """Handler must not be entered when Content-Length > 1 MiB."""
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
            body = b"x" * (ONE_MIB + 100)
            r = await c.post(
                "/scan-email",
                content=body,
                headers={"Content-Length": str(len(body)), "Content-Type": "application/json"},
            )
            assert r.status_code == 413
            assert not handler_entered, "Handler entered for oversized request"
    finally:
        bm.scan_email = original
