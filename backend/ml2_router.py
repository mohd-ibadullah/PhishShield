# -*- coding: utf-8 -*-
"""ML2 router: language -> specialist leg. Frozen config: ml2/ROUTER.yaml.
Routing, not fusion: one specialist decides per email. No new cross-model score averaging.
Honest failure: unknown language / model failure -> None (caller surfaces 'could not classify
confidently'), never local-heuristics-as-verdict.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
ROUTER_YAML_PATH = REPO_ROOT / "ml2" / "ROUTER.yaml"
LABEL_MAP_PATH = REPO_ROOT / "ml2" / "label_map.json"
V2_MODEL_DIR = REPO_ROOT / "model_merged"

# Unicode script ranges (supersets of what the legacy rule layer uses)
_SCRIPT_RANGES: tuple[tuple[str, tuple[int, int]], ...] = (
    ("devanagari", (0x0900, 0x097F)),
    ("arabic", (0x0600, 0x06FF)),
    ("tamil", (0x0B80, 0x0BFF)),
    ("bengali", (0x0980, 0x09FF)),
    ("telugu", (0x0C00, 0x0C7F)),
)

_HINGLISH_TOKEN_RE = re.compile(
    r"\b(koi|hafte|hai|nahi|abhi|bhejo|karo|aapke|aapka|kal|ghar|paisa)\b", re.IGNORECASE
)

_ROUTER_STATE: dict[str, Any] = {
    "config": None,
    "label_map": None,
    "v2_model": None,
    "v2_tokenizer": None,
    "v2_loaded": False,
    "v2_failed": False,
}


def _load_router_config() -> dict[str, Any] | None:
    """Parse ROUTER.yaml without a yaml dependency: block-style key: value / nesting by indent."""
    if _ROUTER_STATE["config"] is not None:
        return _ROUTER_STATE["config"]
    try:
        import yaml  # type: ignore

        with open(ROUTER_YAML_PATH, encoding="utf-8") as fh:
            _ROUTER_STATE["config"] = yaml.safe_load(fh)
        return _ROUTER_STATE["config"]
    except ImportError:
        pass
    except Exception:
        logger.exception("ROUTER.yaml parse failed")
        return None
    # Minimal fallback parser (no PyYAML): not needed if PyYAML exists (FastAPI stacks usually ship it).
    logger.warning("PyYAML unavailable; ROUTER.yaml not parsed — router runs in honest-failure mode")
    return None


def _load_label_map() -> dict[str, Any] | None:
    if _ROUTER_STATE["label_map"] is not None:
        return _ROUTER_STATE["label_map"]
    try:
        with open(LABEL_MAP_PATH, encoding="utf-8") as fh:
            _ROUTER_STATE["label_map"] = json.load(fh)
        return _ROUTER_STATE["label_map"]
    except Exception:
        logger.exception("label_map.json load failed")
        return None


def _detect_script_language(text: str) -> str | None:
    """Script-based detection beyond the legacy HI/TE detector: ur/ta/bn + dense Devanagari/Telugu."""
    visible = [c for c in text if not c.isspace()]
    total = len(visible)
    if total == 0:
        return None
    counts: dict[str, int] = {}
    for name, (lo, hi) in _SCRIPT_RANGES:
        n = sum(1 for c in visible if lo <= ord(c) <= hi)
        if n:
            counts[name] = n
    if not counts:
        # Hinglish: Latin-script code-mixed Hindi tokens
        if _HINGLISH_TOKEN_RE.search(text):
            return "MX"
        return "EN"
    top = max(counts.items(), key=lambda kv: kv[1])
    if top[1] / total >= 0.15:
        return {
            "devanagari": "HI",
            "telugu": "TE",
            "arabic": "UR",
            "tamil": "TA",
            "bengali": "BN",
        }[top[0]]
    return "MX" if _HINGLISH_TOKEN_RE.search(text) else "EN"


def detect_route_language(text: str) -> str:
    """HI/TE/UR/TA/BN -> non-Latin route; MX -> Hinglish; EN -> english."""
    return _detect_script_language(text or "")


def _ensure_v2_loaded() -> bool:
    if _ROUTER_STATE["v2_loaded"]:
        return True
    if _ROUTER_STATE["v2_failed"]:
        return False
    try:
        import torch  # type: ignore
        from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore

        tok = AutoTokenizer.from_pretrained(str(V2_MODEL_DIR), local_files_only=True)
        mdl = AutoModelForSequenceClassification.from_pretrained(str(V2_MODEL_DIR), local_files_only=True)
        mdl.eval()
        _ROUTER_STATE["v2_model"] = mdl
        _ROUTER_STATE["v2_tokenizer"] = tok
        _ROUTER_STATE["v2_loaded"] = True
        logger.info("ML2 router: V2 XLM-R loaded from %s", V2_MODEL_DIR)
        return True
    except Exception:
        logger.exception("ML2 router: V2 model load failed — non-Latin route goes honest-failure")
        _ROUTER_STATE["v2_failed"] = True
        return False


def _v2_predict(text: str) -> dict[str, Any] | None:
    """V2 XLM-R inference. Returns {argmax, probs, score} or None on failure.
    Dead-class guard: argmax == 1 -> unresolved (never silently mapped to ham/phish)."""
    if not _ensure_v2_loaded():
        return None
    try:
        import torch  # type: ignore

        tok = _ROUTER_STATE["v2_tokenizer"]
        mdl = _ROUTER_STATE["v2_model"]
        enc = tok(text, truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            probs = torch.softmax(mdl(**enc).logits, dim=-1)[0].tolist()
        argmax = int(max(range(len(probs)), key=lambda i: probs[i]))
        return {"argmax": argmax, "probs": [round(float(p), 4) for p in probs], "score": float(probs[argmax])}
    except Exception:
        logger.exception("ML2 router: V2 inference failed")
        return None


def _muril_predict(text: str) -> dict[str, Any] | None:
    """MuRIL standalone leg (MX route). Self-contained torch inference off the
    shared provider (get_tokenizer/get_model) — no main import (circular).
    Label convention matches the ensemble: index 1 = phishing."""
    try:
        from models.muril_provider import MurilProvider  # type: ignore

        import torch  # type: ignore

        provider = MurilProvider()
        tok = provider.get_tokenizer()
        mdl = provider.get_model()
        if tok is None or mdl is None:
            return None
        enc = tok([text], return_tensors="pt", truncation=True, padding=True, max_length=512)
        try:
            device = str(next(mdl.parameters()).device)
        except Exception:
            device = "cpu"
        if "cuda" in device:
            enc = {k: v.to("cuda") for k, v in enc.items()}
        mdl.eval()
        with torch.no_grad():
            probs = torch.softmax(mdl(**enc).logits, dim=-1)[0].tolist()
        if len(probs) < 2:
            return None
        phish_prob = float(max(0.0, min(1.0, probs[1])))
        return {"prob": phish_prob, "score": phish_prob}
    except Exception:
        logger.exception("ML2 router: MuRIL leg failed on MX route")
        return None


def route_verdict(email_text: str) -> dict[str, Any] | None:
    """Top-level router entry. Returns a decision dict or None (honest 'not confident').

    Never throws. Never falls back to local heuristics pretending to be a verdict.
    """
    text = str(email_text or "")
    lang = detect_route_language(text)
    leg: str
    decision: dict[str, Any] | None = None

    if lang in {"HI", "TE", "UR", "TA", "BN"}:
        leg = "v2_xlmr"
        result = _v2_predict(text)
        if result is None:
            return None  # honest failure
        if result["argmax"] == 1:
            # dead-class guard (ROUTER.yaml dead_class_guard)
            email_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            logger.warning(
                json.dumps({"email_sha256": email_sha, "leg": leg, "score": result["score"], "note": "dead_class_emitted"})
            )
            return {"leg": leg, "language": lang, "verdict": None, "confidence": result["score"], "status": "unresolved_dead_class"}
        verdict = "phishing" if result["argmax"] == 0 else "ham"
        decision = {"leg": leg, "language": lang, "verdict": verdict, "confidence": result["score"], "status": "ok", "probs": result["probs"]}
    elif lang == "MX":
        leg = "muril"
        result = _muril_predict(text)
        if result is None:
            return None  # honest failure
        prob = float(result["prob"])
        decision = {"leg": leg, "language": lang, "verdict": "phishing" if prob >= 0.5 else "ham", "confidence": prob, "status": "ok"}
    else:
        leg = "ensemble"
        try:
            ensemble = ensemble_score_ref(text)  # injected late to avoid import cycle
            providers_used = list(ensemble.get("providers_used") or [])
            if not any(name in providers_used for name in ("securebert", "muril")):
                return None  # providers not ready: honest failure, no TF-IDF fake-verdict
            score = float(ensemble.get("score", 0.0))
            decision = {"leg": leg, "language": lang, "verdict": "phishing" if score >= 0.5 else "ham", "confidence": score, "status": "ok"}
        except Exception:
            logger.exception("ML2 router: ensemble leg failed on EN route")
            return None

    if decision is not None:
        decision["email_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        logger.info(
            "ML2 route: leg=%s lang=%s verdict=%s conf=%.3f sha=%s",
            decision["leg"], decision["language"], decision["verdict"], decision["confidence"], decision["email_sha256"],
        )
    return decision


def ensemble_score_ref(text: str) -> dict[str, Any]:
    """Late-bound reference to main.ensemble_score to avoid a circular import at module load."""
    from main import ensemble_score  # type: ignore

    return ensemble_score(text)


def router_boot_report() -> dict[str, Any]:
    """R3: startup paste — which legs are live, config sha, model load state."""
    cfg = _load_router_config()
    lm = _load_label_map()
    return {
        "router_config_present": cfg is not None,
        "label_map_present": lm is not None,
        "label_map_mapping": (lm or {}).get("mapping"),
        "label1_unreachable": (lm or {}).get("label1_unreachable"),
        "v2_model_dir": str(V2_MODEL_DIR),
        "v2_model_present": V2_MODEL_DIR.exists(),
        "v2_loaded": _ROUTER_STATE["v2_loaded"],
        "v2_load_failed": _ROUTER_STATE["v2_failed"],
    }
