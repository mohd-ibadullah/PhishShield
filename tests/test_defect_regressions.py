from __future__ import annotations

import json
from pathlib import Path
import pytest
from httpx import AsyncClient

from services.metrics_service import build_api_metrics_payload
import main as backend_main


def test_metrics_service_returns_none_fpr_when_metadata_lacks_confusion_matrix(monkeypatch, tmp_path: Path) -> None:
    """
    REGRESSION TEST (Defect 2):
    When training_meta.json contains only standard metrics without fp/tn/fpr,
    false_positive_rate must be None (not a fabricated 0.0).
    """
    dummy_meta = {
        "trained_at": "2026-08-28T00:00:00Z",
        "train_rows": 1000,
        "test_rows": 200,
        "metrics": {
            "accuracy": 0.95,
            "precision": 0.94,
            "recall": 0.96,
            "f1_score": 0.95,
        },
    }
    meta_path = tmp_path / "training_meta.json"
    meta_path.write_text(json.dumps(dummy_meta), encoding="utf-8")
    monkeypatch.setattr("services.metrics_service.resolve_training_metadata_path", lambda: meta_path)

    payload = build_api_metrics_payload([])
    assert payload["offline_evaluation"]["false_positive_rate"] is None, (
        f"Expected None when fp/tn/fpr absent in metadata, got {payload['offline_evaluation']['false_positive_rate']}"
    )


@pytest.mark.asyncio
async def test_health_endpoint_has_no_numeric_metrics_when_metadata_missing(monkeypatch, client: AsyncClient) -> None:
    """
    REGRESSION TEST (Defect 1):
    When training_meta.json is missing or lacks metrics, /health accuracy and f1_score
    must return '—' (never fabricated numbers like 98.9% or 98.6%).
    """
    monkeypatch.setattr(backend_main, "load_training_metadata", lambda: {})
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["accuracy"] == "—", f"Expected '—' for accuracy when metadata missing, got {body['accuracy']}"
    assert body["f1_score"] == "—", f"Expected '—' for f1_score when metadata missing, got {body['f1_score']}"
