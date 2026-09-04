from __future__ import annotations

import pytest

import main as backend_main
from explain import explain_prediction


@pytest.mark.asyncio
async def test_scan_email_includes_runtime_explanation(client, sample_emails, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "save_scan_to_db", lambda *args, **kwargs: None)
    response = await client.post("/scan-email", json={"email_text": sample_emails["otp_scam"]})
    assert response.status_code == 200

    payload = response.json()
    explanation = payload.get("explanation") or {}
    assert isinstance(explanation.get("top_words"), list)
    assert explanation.get("method") in {"shap", "lime", "linear-weights", "heuristic"}
    # Default scan path skips SHAP unless PHISHSHIELD_TRY_SHAP_ON_SCAN=1
    if not __import__("os").getenv("PHISHSHIELD_TRY_SHAP_ON_SCAN"):
        assert explanation.get("method") in {"linear-weights", "lime", "heuristic"}
    assert explanation.get("confidence_interval")
    assert "% ±" in str(explanation.get("confidence_interval"))


def test_explain_prediction_skip_shap_returns_fast_fallback() -> None:
    result = explain_prediction(
        "URGENT: verify your OTP immediately.",
        risk_score=70,
        signal_count=2,
        confidence_percent=80,
        skip_shap=True,
    )
    assert result["method"] in {"linear-weights", "lime", "heuristic"}
    assert isinstance(result.get("top_words"), list)


def test_explain_prediction_shap_timeout_falls_back(monkeypatch) -> None:
    import explain as explain_module

    monkeypatch.setattr(explain_module, "TRY_SHAP_ON_SCAN", True)
    monkeypatch.setattr(
        explain_module,
        "_shap_tfidf_explanation",
        lambda *args, **kwargs: ([], "shap_timeout"),
    )

    result = explain_prediction(
        "verify OTP now",
        risk_score=70,
        signal_count=2,
    )
    assert result.get("explanation_degraded") is True
    assert result.get("degraded_reason") == "shap_timeout"
    assert result["method"] in {"linear-weights", "lime", "heuristic"}


def test_explain_prediction_returns_method_and_words() -> None:
    backend_main.load_artifacts()
    if backend_main.artifacts.model is None or backend_main.artifacts.vectorizer is None:
        pytest.skip("TF-IDF artifacts not available in this environment")

    result = explain_prediction(
        "URGENT: verify your OTP immediately to avoid account suspension.",
        risk_score=82,
        signal_count=3,
        confidence_percent=91,
        model=backend_main.artifacts.model,
        vectorizer=backend_main.artifacts.vectorizer,
        predictor=lambda texts: backend_main.artifacts.model.predict_proba(
            backend_main.artifacts.vectorizer.transform(
                [backend_main.clean_text(text) for text in texts]
            )
        )[:, 1],
    )

    assert result["method"] in {"shap", "lime", "linear-weights", "heuristic"}
    assert isinstance(result.get("top_words"), list)
    assert str(result.get("confidence_interval", "")).startswith("91%")


@pytest.mark.asyncio
async def test_retrain_rejects_invalid_feedback_labels(client, monkeypatch, tmp_path) -> None:
    # Uses the conftest default configured key; the internal header is required
    # post-b3.1 (unset/placeholder key now denies with 403, tested separately).
    feedback_path = tmp_path / "feedback.csv"
    state_path = tmp_path / "feedback_state.json"
    dataset_path = tmp_path / "Phishing_Email.csv"
    dataset_path.write_text(
        "Email Text,Email Type\n"
        "benign notice,Safe Email\n"
        "urgent otp scam,Phishing Email\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", feedback_path)
    monkeypatch.setattr(backend_main, "FEEDBACK_STATE_PATH", state_path)
    monkeypatch.setattr(backend_main, "DATASET_PATH", dataset_path)
    monkeypatch.setattr(backend_main, "RETRAIN_MIN_TRAINING_ROWS", 2)
    # Lower the sample threshold so label validation runs before the count check
    monkeypatch.setattr(backend_main, "RETRAIN_THRESHOLD", 1)
    backend_main.ensure_feedback_store()
    feedback_path.write_text(
        "email_text,user_label,model_prediction,timestamp,scan_id\n"
        "bad label email,unknown,phishing,2026-01-01T00:00:00Z,abc\n",
        encoding="utf-8",
    )

    response = await client.post("/retrain", headers={"x-internal-api-key": "test-internal-key"})
    assert response.status_code == 400
    assert "Unsupported feedback labels" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_feedback_api_alias_matches_primary_route(client, sample_emails, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "save_scan_to_db", lambda *args, **kwargs: None)
    scan_response = await client.post("/scan-email", json={"email_text": sample_emails["otp_scam"]})
    assert scan_response.status_code == 200
    scan_id = scan_response.json().get("scan_id")

    payload = {
        "email_text": sample_emails["otp_scam"],
        "correct_label": "safe",
        "scan_id": scan_id,
    }
    primary = await client.post("/feedback", json=payload)
    alias = await client.post("/api/feedback", json=payload)
    assert primary.status_code == 200
    assert alias.status_code == 200
    assert primary.json().get("saved") is True
    assert alias.json().get("saved") is True


@pytest.mark.asyncio
async def test_feedback_stats_api_alias(client) -> None:
    # Session auth now required for /feedback/stats (T0-T15 hardening)
    await client.post("/api/session")
    primary = await client.get("/feedback/stats")
    alias = await client.get("/api/feedback/stats")
    assert primary.status_code == 200
    assert alias.status_code == 200
    assert primary.json().keys() == alias.json().keys()


@pytest.mark.asyncio
async def test_retrain_requires_feedback_rows(client, monkeypatch, tmp_path) -> None:
    # Uses the conftest default configured key; the internal header is required
    # post-b3.1 (unset/placeholder key now denies with 403, tested separately).
    feedback_path = tmp_path / "feedback.csv"
    state_path = tmp_path / "feedback_state.json"
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", feedback_path)
    monkeypatch.setattr(backend_main, "FEEDBACK_STATE_PATH", state_path)
    backend_main.ensure_feedback_store()

    response = await client.post("/retrain", headers={"x-internal-api-key": "test-internal-key"})
    assert response.status_code == 400
    # With 0 feedback rows, RETRAIN_THRESHOLD (50) check fires first
    detail = response.json().get("detail", "")
    assert "feedback" in detail.lower(), f"Expected feedback-related error, got: {detail}"


@pytest.mark.asyncio
async def test_retrain_forbidden_without_header_when_key_configured(client, monkeypatch) -> None:
    """Key configured: /retrain without or with an invalid key header is 403."""
    monkeypatch.setattr(backend_main, "INTERNAL_API_KEY", "b2-test-internal-key")

    missing = await client.post("/retrain")
    assert missing.status_code == 403
    wrong = await client.post("/retrain", headers={"x-internal-api-key": "wrong-key"})
    assert wrong.status_code == 403


@pytest.mark.asyncio
async def test_retrain_authorized_with_configured_key(client, monkeypatch, tmp_path) -> None:
    """Key configured + valid header passes the guard; empty feedback is still 400."""
    monkeypatch.setattr(backend_main, "INTERNAL_API_KEY", "b2-test-internal-key")
    feedback_path = tmp_path / "feedback.csv"
    state_path = tmp_path / "feedback_state.json"
    monkeypatch.setattr(backend_main, "FEEDBACK_CSV_PATH", feedback_path)
    monkeypatch.setattr(backend_main, "FEEDBACK_STATE_PATH", state_path)
    backend_main.ensure_feedback_store()

    response = await client.post("/retrain", headers={"x-internal-api-key": "b2-test-internal-key"})
    assert response.status_code == 400
    # With 0 feedback rows, RETRAIN_THRESHOLD (50) check fires first
    detail = response.json().get("detail", "")
    assert "feedback" in detail.lower(), f"Expected feedback-related error, got: {detail}"
