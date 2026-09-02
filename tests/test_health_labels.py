"""T5: Health labels must not contain hardcoded metric literals."""
from __future__ import annotations

import re
import sys
import pathlib
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as bm

pytestmark = __import__("pytest").mark.asyncio


async def test_no_hardcoded_metric_literals():
    """Health response must not contain hardcoded percentage strings."""
    transport = ASGITransport(app=bm.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get("/health")
        assert r.status_code == 200
        body = r.json()
        # Check no hardcoded metric strings
        for key in ("accuracy", "f1_score"):
            val = str(body.get(key, ""))
            assert "98.9" not in val, f"{key} contains 98.9: {val}"
            assert "98.6" not in val, f"{key} contains 98.6: {val}"
            assert "97.4" not in val, f"{key} contains 97.4: {val}"


async def test_health_no_percent_when_no_model(monkeypatch):
    """When no model is loaded, health should not report numeric accuracy."""
    monkeypatch.setattr(bm.artifacts, "model", None)
    monkeypatch.setattr(bm.artifacts, "indicbert_model", None)
    monkeypatch.setattr(bm.artifacts, "indicbert_tokenizer", None)
    monkeypatch.setattr(bm, "_securebert_provider", None)
    monkeypatch.setattr(bm, "_muril_provider", None)
    transport = ASGITransport(app=bm.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get("/health")
        assert r.status_code == 200
        body = r.json()
        # Should not contain any percentage
        for key in ("accuracy", "f1_score"):
            val = str(body.get(key, ""))
            assert "%" not in val, f"{key} has '%' when no model loaded: {val}"
