"""ML2 ROUTER pass R4: language-router entry wired into main.calculate_email_risk.

Contract under test (ml2/ROUTER.yaml, frozen 2026-09-11):
1. Non-Latin route (HI/TE/UR/TA/BN) with a confident V2 phishing verdict raises the
   pipeline risk floor to 70 (router_leg=v2_xlmr) — routing, not fusion.
2. The V2 floor is skipped for OTP-safety awareness emails (shared QA-FIX-2 escape
   predicate — no double standard between the rule layer and the router leg).
3. Honest failure: router None (model missing / dead class / unknown language) → the
   existing pipeline result is returned untouched — never local-heuristics-as-verdict.

These tests monkeypatch backend.ml2_router.route_verdict, so no model weights are
needed; the mock returns the same shape route_verdict produces in production.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

main = importlib.import_module("main")
cert = importlib.import_module("certification_run")
ml2_router = importlib.import_module("ml2_router")

# T9 product-gap case (tests/multilingual_test_cases.py::hindi_bank_urgency): pure-Hindi
# phishing with no lookalike domain. Rule-side alone scores 15/100 — TF-IDF cannot score
# pure Devanagari. This is exactly the gap the V2 specialist floor is meant to close.
HINDI_PHISH = (
    "Subject: अत्यावश्यक\nFrom: user1@example.invalid\n"
    "आपके खाते में संदिग्ध गतिविधि। तुरंत लिंक पर क्लिक करें।"
)
# Hindi OTP-awareness email (no links): must stay safe under the shared escape predicate.
HINDI_OTP_AWARENESS = (
    "From: bank@example.invalid\nSubject: सुरक्षा सूचना\n\n"
    "हमारा स्टाफ कभी भी आपसे ओटीपी नहीं मांगता। कृपया अपना OTP किसी के साथ साझा न करें।"
)
ENGLISH_PHISH = (
    "From: user1@example.invalid\nSubject: Account suspended\n\n"
    "Verify your account immediately: http://paypa1.example/verify"
)


@pytest.fixture(autouse=True)
def _init_state() -> None:
    cert._init_app_state()


def _ok_phish(conf: float = 0.95) -> dict:
    return {
        "leg": "v2_xlmr",
        "language": "HI",
        "verdict": "phishing",
        "confidence": conf,
        "status": "ok",
        "probs": [conf, 0.0001, round(1.0 - conf - 0.0001, 4)],
        "email_sha256": "0" * 16,
    }


def _ok_ham(conf: float = 0.95) -> dict:
    d = _ok_phish(conf)
    d["verdict"] = "ham"
    return d


def _unresolved_dead_class(conf: float = 0.55) -> dict:
    d = _ok_phish(conf)
    d["verdict"] = None
    d["status"] = "unresolved_dead_class"
    return d


def test_router_floor_raises_nonlatin_phish_to_70(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_route(text: str) -> dict:
        calls.append(text)
        return _ok_phish()

    monkeypatch.setattr(ml2_router, "route_verdict", fake_route)
    result = main.calculate_email_risk(HINDI_PHISH)

    assert calls, "router leg must be consulted for non-Latin text"
    score = int(result.get("risk_score") or 0)
    assert score >= 70, f"V2 floor not applied: risk={score}"
    assert result.get("router_leg") == "v2_xlmr"
    # Floor semantics, not fusion: the pipeline's own score stays beneath the floor.
    assert score == 70, f"floor must replace (not average) the pipeline score, got {score}"


def test_router_floor_escaped_for_otp_awareness(monkeypatch: pytest.MonkeyPatch) -> None:
    """V2 says phishing, but the shared QA-FIX-2 awareness predicate must keep the
    score at the pipeline's own verdict — no double standard vs. English OTP notices."""

    monkeypatch.setattr(ml2_router, "route_verdict", lambda text: _ok_phish())
    result = main.calculate_email_risk(HINDI_OTP_AWARENESS)

    assert result.get("router_leg") is None, "escape path must not tag router_leg"
    score = int(result.get("risk_score") or 0)
    assert score <= 30, f"OTP-awareness mail must stay safe, got risk={score}"


def test_honest_failure_router_none_leaves_pipeline_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """route_verdict None (model missing / load failure) → pipeline result unchanged,
    router_leg absent — never a faked verdict (ROUTER.yaml fallback_policy)."""

    monkeypatch.setattr(ml2_router, "route_verdict", lambda text: None)
    result_none = main.calculate_email_risk(HINDI_PHISH)

    assert result_none.get("router_leg") is None
    assert int(result_none.get("risk_score") or 0) < 70, (
        "honest failure must return the raw pipeline score (15 for this case), "
        "not a raised or faked one"
    )


def test_dead_class_and_low_confidence_do_not_raise_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ml2_router, "route_verdict", lambda text: _unresolved_dead_class())
    dead = main.calculate_email_risk(HINDI_PHISH)
    assert dead.get("router_leg") is None
    assert int(dead.get("risk_score") or 0) < 70

    monkeypatch.setattr(ml2_router, "route_verdict", lambda text: _ok_phish(conf=0.55))
    low_conf = main.calculate_email_risk(HINDI_PHISH)
    assert low_conf.get("router_leg") is None
    assert int(low_conf.get("risk_score") or 0) < 70


def test_english_path_never_enters_router_leg(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_route(text: str) -> dict:
        calls.append(text)
        return _ok_phish()

    monkeypatch.setattr(ml2_router, "route_verdict", fake_route)
    result = main.calculate_email_risk(ENGLISH_PHISH)

    assert not calls, "EN route belongs to the ensemble leg, not the V2 specialist"
    assert result.get("router_leg") is None


def test_router_boot_report_shape() -> None:
    """R3: boot report must honestly report config/label-map/model presence."""
    report = ml2_router.router_boot_report()
    assert report["router_config_present"] is True
    assert report["label_map_present"] is True
    assert report["label1_unreachable"] is True
    assert report["label_map_mapping"] == {
        "LABEL_0": "phishing",
        "LABEL_1": None,
        "LABEL_2": "ham",
    }
    # Frozen weights sha from MODEL_ARTIFACTS.md / ROUTER.yaml — registry must agree.
    assert report["v2_model_present"] == Path(main.__file__).parent.parent.joinpath("model_merged").exists()
