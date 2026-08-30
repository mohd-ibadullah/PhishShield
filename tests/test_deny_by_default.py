"""Deny-by-default contract for the internal API key (W2 / b3.1).

The app must refuse to start when PHISHSHIELD_INTERNAL_API_KEY is unset or
still the exact .env.example placeholder, and protected endpoints must deny
(403) in that state instead of failing open.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main as backend_main

PLACEHOLDER = "change-me"  # exact placeholder in .env.example


def test_startup_validator_refuses_unset_key(monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "INTERNAL_API_KEY", "")
    with pytest.raises(RuntimeError, match="PHISHSHIELD_INTERNAL_API_KEY"):
        backend_main.validate_internal_key_configuration()


def test_startup_validator_refuses_placeholder_key(monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "INTERNAL_API_KEY", PLACEHOLDER)
    with pytest.raises(RuntimeError, match="PHISHSHIELD_INTERNAL_API_KEY"):
        backend_main.validate_internal_key_configuration()


def test_startup_validator_accepts_configured_key(monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "INTERNAL_API_KEY", "b31-valid-test-key")
    backend_main.validate_internal_key_configuration()  # must not raise


def test_startup_refusal_runs_via_testclient_lifespan(monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "INTERNAL_API_KEY", "")
    with pytest.raises(RuntimeError, match="PHISHSHIELD_INTERNAL_API_KEY"):
        with TestClient(backend_main.app):
            pass


@pytest.mark.asyncio
async def test_retrain_forbidden_when_key_unset(client, monkeypatch) -> None:
    """Post-b3.1 contract: unset key denies protected endpoints (no fail-open)."""
    monkeypatch.setattr(backend_main, "INTERNAL_API_KEY", "")
    response = await client.post("/retrain")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_retrain_forbidden_when_key_is_placeholder(client, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "INTERNAL_API_KEY", PLACEHOLDER)
    response = await client.post("/retrain", headers={"x-internal-api-key": PLACEHOLDER})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_feedback_stats_hides_retrain_threshold(client) -> None:
    response = await client.get("/feedback/stats")
    assert response.status_code == 200
    assert "retrain_threshold" not in response.json()
