"""T11: Retrain threshold and feedback limits."""
from __future__ import annotations

import sys
import pathlib
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as bm

pytestmark = __import__("pytest").mark.asyncio


async def test_retrain_locked_below_threshold(monkeypatch):
    """Retrain should fail when pending feedback < RETRAIN_THRESHOLD."""
    monkeypatch.setattr(bm, "RETRAIN_THRESHOLD", 100)
    monkeypatch.setattr(bm, "INTERNAL_API_KEY", "test-key-12345")
    # Mock count_pending_retrain_samples to return 5
    monkeypatch.setattr(bm, "count_pending_retrain_samples", lambda: 5)

    transport = ASGITransport(app=bm.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post(
            "/retrain",
            headers={"x-internal-api-key": "test-key-12345"},
        )
        assert r.status_code == 400
        assert "100" in r.json()["detail"] or "threshold" in r.json()["detail"].lower()
