from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent


def training_metadata_paths() -> list[Path]:
    """Canonical metadata is tracked once at the repository data path."""
    return [BASE_DIR.parent / "data" / "training_meta.json"]


HEADLINES_OUTPUT_PATH = BASE_DIR.parent / "diagnostics" / "headlines_output.json"


def load_system_eval() -> dict[str, Any] | None:
    """End-to-end system performance: full pipeline (routing + rules + merge)
    scored on the OOD holdout via the live /scan endpoint. None when the
    harness output is absent.
    """
    if not HEADLINES_OUTPUT_PATH.exists():
        return None
    try:
        payload = json.loads(HEADLINES_OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    system_eval = payload.get("system_eval")
    return system_eval if isinstance(system_eval, dict) else None


def load_benchmark_caveat() -> dict[str, Any] | None:
    """Caveat counts produced by diagnostics/reproduce_headlines.py, or None.

    The dashboard renders the committed-dataset caveat only when this harness
    output is present; an absent or unreadable file means no caveat is shown.
    """
    if not HEADLINES_OUTPUT_PATH.exists():
        return None
    try:
        payload = json.loads(HEADLINES_OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    caveat = payload.get("caveat")
    if not isinstance(caveat, dict):
        return None
    required = ("csv_records", "template_families", "families_shared_between_classes")
    if not all(isinstance(caveat.get(key), int) for key in required):
        return None
    return {key: caveat[key] for key in required}


def resolve_training_metadata_path() -> Path | None:
    for candidate in training_metadata_paths():
        if candidate.exists():
            return candidate
    return None


def load_training_metadata() -> dict[str, Any]:
    path = resolve_training_metadata_path()
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


FEEDBACK_MEMORY_PATH = BASE_DIR.parent / "data" / "feedback_memory.json"


def _learning_metrics_from_feedback() -> dict[str, Any]:
    """Live Session Accuracy inputs, computed from the persisted feedback store.

    Agreement = model verdict matched the analyst-corrected verdict.
    A correction is a false positive when the model flagged phish/suspicious
    but the analyst said Safe; a false negative is the reverse.
    """
    empty = {
        "feedback_samples": 0,
        "confirmed_correct": 0,
        "false_positive_count": 0,
        "false_negative_count": 0,
        "feedback_agreement_rate": None,
        "pending_review_count": 0,
    }
    if not FEEDBACK_MEMORY_PATH.exists():
        return empty
    try:
        payload = json.loads(FEEDBACK_MEMORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    entries = payload.get("entries") if isinstance(payload.get("entries"), dict) else {}
    samples = confirmed = fp = fn = pending_review = 0
    for entry in entries.values():
        if not isinstance(entry, dict):
            continue
        predicted = str(entry.get("predicted") or "").strip().lower()
        corrected = str(entry.get("corrected") or "").strip().lower()
        if predicted and not corrected:
            pending_review += 1
        if not predicted or not corrected:
            continue
        samples += 1
        if predicted == corrected:
            confirmed += 1
        elif corrected == "safe":
            fp += 1
        elif corrected in {"high risk", "high"}:
            fn += 1
    rate = (confirmed / samples) if samples else None
    return {
        "feedback_samples": samples,
        "confirmed_correct": confirmed,
        "false_positive_count": fp,
        "false_negative_count": fn,
        "feedback_agreement_rate": rate,
        "pending_review_count": pending_review,
    }


def _runtime_counts_from_scans(scans: list[dict[str, Any]]) -> dict[str, int]:
    total_scans = len(scans)
    phishing_detected = sum(1 for item in scans if int(item.get("risk_score", 0) or 0) >= 61)
    suspicious_detected = sum(1 for item in scans if 26 <= int(item.get("risk_score", 0) or 0) <= 60)
    safe_detected = max(total_scans - phishing_detected - suspicious_detected, 0)
    return {
        "total_scans": total_scans,
        "phishing_detected": phishing_detected,
        "suspicious_detected": suspicious_detected,
        "safe_detected": safe_detected,
    }


def build_api_metrics_payload(scans: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Honest metrics payload: offline holdout evaluation vs in-process runtime counters.
    """
    metadata = load_training_metadata()
    offline_raw = metadata.get("metrics") if isinstance(metadata.get("metrics"), dict) else {}
    runtime = _runtime_counts_from_scans(scans)
    learning = _learning_metrics_from_feedback()

    accuracy = float(offline_raw.get("accuracy", 0.0) or 0.0)
    precision = float(offline_raw.get("precision", 0.0) or 0.0)
    recall = float(offline_raw.get("recall", 0.0) or 0.0)
    f1 = float(offline_raw.get("f1_score", offline_raw.get("f1Score", 0.0)) or 0.0)
    # Honest False Positive Rate: FP / (FP + TN)
    fpr_val = offline_raw.get("fpr", offline_raw.get("false_positive_rate"))
    if fpr_val is not None:
        false_positive_rate = float(fpr_val)
    elif "fp" in offline_raw and "tn" in offline_raw:
        fp_count = float(offline_raw["fp"])
        tn_count = float(offline_raw["tn"])
        false_positive_rate = fp_count / max(1.0, fp_count + tn_count)
    else:
        false_positive_rate = None

    live_qa = metadata.get("live_qa") if isinstance(metadata.get("live_qa"), dict) else {}
    live_range = live_qa.get("estimated_accuracy_range")
    live_accuracy_note = None
    if isinstance(live_range, (list, tuple)) and len(live_range) == 2:
        try:
            low = float(live_range[0])
            high = float(live_range[1])
            live_accuracy_note = f"Documented live UI QA range: {low * 100:.0f}–{high * 100:.0f}% (May 2026 sample)"
        except (TypeError, ValueError):
            live_accuracy_note = None

    ood_raw = metadata.get("ood_holdout") if isinstance(metadata.get("ood_holdout"), dict) else {}
    ood_available = ood_raw.get("available") is not False and bool(ood_raw)

    def _ood_metric(key: str) -> float | None:
        if not ood_available:
            return None
        try:
            value = ood_raw.get(key)
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    offline_evaluation = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "false_positive_rate": false_positive_rate,
        # Honest generalization measurement (hand-authored adversarial holdout,
        # disjoint from the training CSV). Null when the holdout is absent.
        "ood_holdout": {
            "source": ood_raw.get("source"),
            "rows": _ood_metric("rows"),
            "accuracy": _ood_metric("accuracy"),
            "precision": _ood_metric("precision"),
            "recall": _ood_metric("recall"),
            "f1_score": _ood_metric("f1_score"),
            "false_positive_rate": _ood_metric("false_positive_rate"),
            "note": ood_raw.get("note") if ood_available else None,
            "available": ood_available,
        },
        "evaluated_at": metadata.get("trained_at"),
        "evaluation_dataset_size": metadata.get("test_rows"),
        "training_rows": metadata.get("train_rows"),
        "model_type": metadata.get("model_type"),
        "training_metadata_version": metadata.get("trained_at"),
        "metadata_path": str(resolve_training_metadata_path() or training_metadata_paths()[0]),
        "disclaimer": "Offline holdout evaluation on a fixed train/test split — not continuously measured live accuracy.",
        "live_qa_note": live_accuracy_note,
        "system_eval": load_system_eval(),
        "benchmark_caveat": load_benchmark_caveat(),
    }

    runtime_operational = {
        **runtime,
        "scope": "current_process_session_memory",
        "disclaimer": "Counts reflect scans stored in this API process session, not global production telemetry.",
    }

    return {
        "metrics_kind": "offline_evaluation_plus_runtime_operational",
        "offline_evaluation": offline_evaluation,
        "runtime_operational": runtime_operational,
        # Backward-compatible flat keys (explicitly sourced from offline evaluation)
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1Score": f1,
        "falsePositiveRate": false_positive_rate,
        "accuracy_source": "offline_holdout_evaluation",
        "totalScans": runtime["total_scans"],
        "phishingDetected": runtime["phishing_detected"],
        "suspiciousDetected": runtime["suspicious_detected"],
        "safeDetected": runtime["safe_detected"],
        **({
            "feedbackSamples": learning["feedback_samples"],
            "confirmedCorrect": learning["confirmed_correct"],
            "falsePositiveCount": learning["false_positive_count"],
            "falseNegativeCount": learning["false_negative_count"],
            "feedbackAgreementRate": learning["feedback_agreement_rate"],
        } if learning["feedback_samples"] else {}),
        "driftLevel": "low" if not learning["feedback_samples"] else (
            "high" if learning["feedback_agreement_rate"] is not None and learning["feedback_agreement_rate"] < 0.5
            else "medium" if learning["feedback_agreement_rate"] is not None and learning["feedback_agreement_rate"] < 0.8
            else "low"
        ),
        "falseNegativeCount": learning["false_negative_count"],
        # Honest drift score: disagreement share of reviewed feedback (0.0 = perfect agreement).
        "driftScore": (
            round(1.0 - learning["feedback_agreement_rate"], 4)
            if learning["feedback_agreement_rate"] is not None
            else None
        ),
        # Entries with a model prediction but no analyst correction yet.
        "needsReviewCount": learning["pending_review_count"],
        # Retrain recommendation mirrors the drift contract: medium+ drift means retrain.
        "retrainingRecommended": (
            learning["feedback_samples"] > 0
            and learning["feedback_agreement_rate"] is not None
            and learning["feedback_agreement_rate"] < 0.8
        ),
        "samplesSinceLastRetrain": runtime["total_scans"],
    }
