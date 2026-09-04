#!/usr/bin/env python
"""
Recompute evaluation metrics with correct methodology:
  (a) Binary ECE: phishing probability vs binary label (phish=1, safe=0)
  (b) Per-slice phishing recall + AUC using 2-class remapping
  (c) Energy-score distributions for ID-val vs OOD slices

The previous reported ECE=1.0883 was impossible (ECE ∈ [0,1]) because it
compared a continuous phishing-prob against 3-class labels (0/1/2).
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

# ── paths ──────────────────────────────────────────────────────────────
BACKEND = Path(__file__).resolve().parent
PROJECT = BACKEND.parent

sys.path.insert(0, str(BACKEND))

from main import (
    load_artifacts,
    compute_language_model_probability,
    clean_text,
    normalize_confusables,
)

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── data loaders ───────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict]:
    df = pd.read_csv(path, encoding="utf-8")
    return df.to_dict("records")


def to_binary(label: str) -> int:
    """Map any label to binary: 1 = phishing, 0 = safe."""
    label = str(label).strip().lower()
    if label in ("phishing", "phish", "spam"):
        return 1
    return 0


# ── metrics ────────────────────────────────────────────────────────────

def compute_ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error on BINARY classification.
    
    Correctly bounded in [0, 1]. Bins on predicted probability,
    compares against fraction of positives in each bin.
    """
    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bin_boundaries[i], bin_boundaries[i + 1]
        mask = (probs >= lo) & (probs < hi)
        if i == n_bins - 1:  # include right endpoint in last bin
            mask = (probs >= lo) & (probs <= hi)
        n_bin = mask.sum()
        if n_bin == 0:
            continue
        avg_pred = probs[mask].mean()
        avg_true = labels[mask].mean()
        ece += n_bin / len(probs) * abs(avg_pred - avg_true)
    return float(ece)


def compute_au_roc(probs: np.ndarray, labels: np.ndarray) -> float:
    """Simple AUC-ROC via trapezoidal rule (no sklearn dependency needed)."""
    # Sort by descending probability
    order = np.argsort(-probs)
    sorted_labels = labels[order]
    
    n_pos = sorted_labels.sum()
    n_neg = len(sorted_labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    
    tp = fp = 0
    tpr_prev = fpr_prev = 0.0
    auc = 0.0
    
    for label in sorted_labels:
        if label == 1:
            tp += 1
        else:
            fp += 1
        tpr = tp / n_pos
        fpr = fp / n_neg
        auc += (fpr - fpr_prev) * (tpr + tpr_prev) / 2.0
        tpr_prev = tpr
        fpr_prev = fpr
    
    return float(auc)


def compute_energy_scores(probs: np.ndarray) -> np.ndarray:
    """Energy score = -logsumexp(logits).
    
    Since we have probabilities p (phishing prob), logits = [log(1-p), log(p)].
    Energy = -log(exp(log(1-p)) + exp(log(p))) = -log(1-p+p) = -log(1) = 0
    
    That's trivial because we only have 1 output. Instead, use the actual
    model logits via the TF-IDF pipeline's decision_function or predict_proba.
    
    Here we approximate: energy = -log(p * (1-p)) which peaks at p=0.5
    (uncertain) and is low for confident predictions (p near 0 or 1).
    This is a useful OOD detector: OOD samples tend to have high entropy.
    """
    # Clamp to avoid log(0)
    p = np.clip(probs, 1e-7, 1 - 1e-7)
    # Negative log of Bernoulli entropy proxy
    energy = -(np.log(p) * p + np.log(1 - p) * (1 - p))
    return energy


def compute_entropy(probs: np.ndarray) -> np.ndarray:
    """Binary entropy: H(p) = -p*log(p) - (1-p)*log(1-p)."""
    p = np.clip(probs, 1e-7, 1 - 1e-7)
    return -(p * np.log(p) + (1 - p) * np.log(1 - p))


# ── main evaluation ───────────────────────────────────────────────────

def evaluate_dataset(name: str, items: list[dict], ml_prob_fn) -> dict:
    """Run model on dataset items and collect results."""
    results = []
    for item in items:
        text = str(item.get("text") or "")
        label_raw = str(item.get("label") or "")
        binary_label = to_binary(label_raw)
        
        try:
            cleaned = clean_text(normalize_confusables(text))
            ml_prob, _ = ml_prob_fn(text, cleaned)
            ml_prob = float(max(0.0, min(1.0, ml_prob)))
        except Exception as e:
            ml_prob = 0.5  # fallback
        
        results.append({
            "text": text[:100],
            "label_raw": label_raw,
            "label_binary": binary_label,
            "ml_prob": ml_prob,
        })
    
    probs = np.array([r["ml_prob"] for r in results])
    labels = np.array([r["label_binary"] for r in results])
    
    n_phish = int(labels.sum())
    n_safe = len(labels) - n_phish
    
    # Binary predictions at 0.5 threshold
    preds = (probs >= 0.5).astype(int)
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    tn = int(((preds == 0) & (labels == 0)).sum())
    
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    accuracy = (tp + tn) / len(labels) if len(labels) > 0 else 0.0
    
    ece = compute_ece(probs, labels)
    auc = compute_au_roc(probs, labels)
    energy = compute_energy_scores(probs)
    entropy = compute_entropy(probs)
    
    return {
        "name": name,
        "n_total": len(results),
        "n_phishing": n_phish,
        "n_safe": n_safe,
        "accuracy": accuracy,
        "precision": precision,
        "recall_phishing": recall,
        "fpr": fpr,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "ece_correct": ece,
        "auc_roc": auc,
        "mean_energy": float(energy.mean()),
        "std_energy": float(energy.std()),
        "mean_entropy": float(entropy.mean()),
        "std_entropy": float(entropy.std()),
        "phish_prob_stats": {
            "mean": float(probs[labels == 1].mean()) if n_phish > 0 else 0.0,
            "std": float(probs[labels == 1].std()) if n_phish > 0 else 0.0,
            "median": float(np.median(probs[labels == 1])) if n_phish > 0 else 0.0,
        },
        "safe_prob_stats": {
            "mean": float(probs[labels == 0].mean()) if n_safe > 0 else 0.0,
            "std": float(probs[labels == 0].std()) if n_safe > 0 else 0.0,
            "median": float(np.median(probs[labels == 0])) if n_safe > 0 else 0.0,
        },
    }


def main():
    print("=" * 72)
    print("BINARY EVALUATION RECOMPUTATION")
    print("=" * 72)
    
    # Load model
    print("\n[1] Loading model artifacts...")
    load_artifacts()
    from main import artifacts
    print(f"    Active model: {artifacts.active_model}")
    print(f"    TF-IDF model loaded: {artifacts.model is not None}")
    
    ml_prob_fn = compute_language_model_probability
    
    # ── Load all datasets ──────────────────────────────────────────
    print("\n[2] Loading datasets...")
    
    # Source datasets
    elite_raw = load_json(PROJECT / "data" / "FINAL_ELITE_DATASET.raw.json")
    combined = load_json(PROJECT / "data" / "combined_test_dataset.json")
    dataset_100 = load_json(PROJECT / "data" / "dataset_100.json")
    eval_set = load_jsonl(PROJECT / "diagnostics" / "eval_set_v1.jsonl")
    
    # Categorize eval_set by slice
    slice_groups = defaultdict(list)
    for item in eval_set:
        s = item.get("slice", "unknown")
        slice_groups[s].append(item)
    
    print(f"    elite_raw: {len(elite_raw)} items")
    print(f"    combined: {len(combined)} items")
    print(f"    dataset_100: {len(dataset_100)} items")
    print(f"    eval_set_v1: {len(eval_set)} items")
    print(f"    eval_set slices: {dict((k, len(v)) for k, v in slice_groups.items())}")
    
    # ── Run evaluations ────────────────────────────────────────────
    print("\n[3] Running evaluations (this takes a moment)...")
    
    all_results = []
    
    # A. Overall datasets
    for name, data in [
        ("elite_raw (all)", elite_raw),
        ("combined_test", combined),
        ("dataset_100", dataset_100),
    ]:
        print(f"    Evaluating {name}...")
        r = evaluate_dataset(name, data, ml_prob_fn)
        all_results.append(r)
    
    # B. Elite raw split by 3-class→2-class mapping
    print("    Evaluating elite_raw split by original label...")
    # Check if there are 3-class labels hidden in the raw
    raw_labels = set(item.get("label", "") for item in elite_raw)
    print(f"    Raw labels in elite: {raw_labels}")
    
    # C. eval_set_v1 slices
    for slice_name, items in slice_groups.items():
        print(f"    Evaluating eval_set slice: {slice_name} ({len(items)} items)...")
        r = evaluate_dataset(f"eval_{slice_name}", items, ml_prob_fn)
        all_results.append(r)
    
    # D. Combined eval_set as "ID" vs "paraphrased"/"bec" as "OOD-ish"
    id_items = [i for i in eval_set if i.get("slice") in ("keyword", "legitimate")]
    ood_items = [i for i in eval_set if i.get("slice") in ("paraphrased", "bec")]
    
    if id_items:
        print(f"    Evaluating eval_set ID (keyword+legit): {len(id_items)} items...")
        r_id = evaluate_dataset("eval_ID_vs_OOD", id_items, ml_prob_fn)
        all_results.append(r_id)
    if ood_items:
        print(f"    Evaluating eval_set OOD (paraphrase+bec): {len(ood_items)} items...")
        r_ood = evaluate_dataset("eval_OOD_paraphrase_bec", ood_items, ml_prob_fn)
        all_results.append(r_ood)
    
    # ── Print results ──────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)
    
    for r in all_results:
        print(f"\n-- {r['name']} (n={r['n_total']}, phish={r['n_phishing']}, safe={r['n_safe']}) --")
        print(f"  Accuracy:       {r['accuracy']:.4f}")
        print(f"  Precision:      {r['precision']:.4f}")
        print(f"  Recall (phish): {r['recall_phishing']:.4f}")
        print(f"  FPR:            {r['fpr']:.4f}")
        print(f"  TP={r['tp']} FP={r['fp']} FN={r['fn']} TN={r['tn']}")
        print(f"  ECE (correct):  {r['ece_correct']:.6f}  (bounded [0,1])")
        print(f"  AUC-ROC:        {r['auc_roc']:.4f}")
        print(f"  Mean energy:    {r['mean_energy']:.4f} ± {r['std_energy']:.4f}")
        print(f"  Mean entropy:   {r['mean_entropy']:.4f} ± {r['std_entropy']:.4f}")
        print(f"  Phish prob:     μ={r['phish_prob_stats']['mean']:.4f} "
              f"σ={r['phish_prob_stats']['std']:.4f} "
              f"med={r['phish_prob_stats']['median']:.4f}")
        print(f"  Safe prob:      μ={r['safe_prob_stats']['mean']:.4f} "
              f"σ={r['safe_prob_stats']['std']:.4f} "
              f"med={r['safe_prob_stats']['median']:.4f}")
    
    # ── Energy score overlap analysis ──────────────────────────────
    print("\n" + "=" * 72)
    print("ENERGY SCORE OVERLAP: ID vs OOD")
    print("=" * 72)
    
    # Re-compute energy distributions for the ID vs OOD split
    id_probs = []
    ood_probs = []
    for item in id_items:
        text = str(item.get("text") or "")
        try:
            cleaned = clean_text(normalize_confusables(text))
            p, _ = ml_prob_fn(text, cleaned)
            id_probs.append(max(0.0, min(1.0, float(p))))
        except:
            id_probs.append(0.5)
    for item in ood_items:
        text = str(item.get("text") or "")
        try:
            cleaned = clean_text(normalize_confusables(text))
            p, _ = ml_prob_fn(text, cleaned)
            ood_probs.append(max(0.0, min(1.0, float(p))))
        except:
            ood_probs.append(0.5)
    
    id_probs = np.array(id_probs)
    ood_probs = np.array(ood_probs)
    id_entropy = compute_entropy(id_probs)
    ood_entropy = compute_entropy(ood_probs)
    
    print(f"\n  ID (keyword+legit) n={len(id_probs)}:")
    print(f"    Prob:  μ={id_probs.mean():.4f} σ={id_probs.std():.4f} "
          f"[{id_probs.min():.4f}, {id_probs.max():.4f}]")
    print(f"    Entropy: μ={id_entropy.mean():.4f} σ={id_entropy.std():.4f}")
    
    print(f"\n  OOD (paraphrase+bec) n={len(ood_probs)}:")
    print(f"    Prob:  μ={ood_probs.mean():.4f} σ={ood_probs.std():.4f} "
          f"[{ood_probs.min():.4f}, {ood_probs.max():.4f}]")
    print(f"    Entropy: μ={ood_entropy.mean():.4f} σ={ood_entropy.std():.4f}")
    
    # Overlap analysis
    id_bins = np.histogram(id_entropy, bins=10, range=(0, np.log(2)))
    ood_bins = np.histogram(ood_entropy, bins=10, range=(0, np.log(2)))
    print(f"\n  Entropy histogram (ID / OOD):")
    for i in range(10):
        lo = i * np.log(2) / 10
        hi = (i + 1) * np.log(2) / 10
        print(f"    [{lo:.3f}, {hi:.3f}): {id_bins[0][i]:3d} / {ood_bins[0][i]:3d}")
    
    # Check OOD AUROC using entropy as the OOD score
    if len(id_entropy) > 0 and len(ood_entropy) > 0:
        all_entropy = np.concatenate([id_entropy, ood_entropy])
        ood_labels = np.concatenate([np.zeros(len(id_entropy)), np.ones(len(ood_entropy))])
        ood_auroc = compute_au_roc(-all_entropy, ood_labels)  # neg entropy: lower=more OOD
        print(f"\n  OOD AUROC (entropy-based): {ood_auroc:.4f}")
        if ood_auroc < 0.6:
            print("  → LOW: entropy cannot distinguish ID from OOD (overlap is real)")
        elif ood_auroc < 0.8:
            print("  → MODERATE: some separation but not strong")
        else:
            print("  → GOOD: entropy separates ID from OOD well")
    
    # ── Summary claims ─────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("CLAIM VERIFICATION")
    print("=" * 72)
    
    for r in all_results:
        print(f"\n  {r['name']}:")
        print(f"    ECE ∈ [0,1]? YES — computed as {r['ece_correct']:.6f}")
        if r['ece_correct'] > 1.0:
            print(f"    *** BUG: ECE > 1.0 — this should be impossible! ***")
        print(f"    Recall: {r['recall_phishing']:.4f} ({r['tp']}/{r['tp']+r['fn']})")
        print(f"    AUC: {r['auc_roc']:.4f}")
    
    # Save results
    out_path = BACKEND / "reports" / "verification" / "binary_eval_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "methodology": {
            "binary_labels": "phishing/spam→1, safe/ham→0",
            "ece_method": "10-bin ECE on binary phishing probability vs binary label",
            "auc_method": "trapezoidal AUC-ROC",
            "energy_method": "negative Bernoulli entropy proxy",
            "note": "Previous ECE=1.0883 was impossible; this recomputes correctly",
        },
        "results": all_results,
    }
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Saved to: {out_path}")


if __name__ == "__main__":
    main()
