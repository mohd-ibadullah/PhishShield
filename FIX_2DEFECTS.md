# Fix Record: Defects Resolved

## Defect 1 — Fabricated Defaults Removed from `/health`
- **File**: `backend/main.py`
- **Function**: `resolve_health_model_fields()`
- **Commit SHA**: `dffb026`
- **Revert**: `git revert dffb026`

### Code Diff:
```diff
--- a/backend/main.py
+++ b/backend/main.py
@@ -1037,8 +1037,8 @@ def resolve_health_model_fields() -> dict[str, str]:
     return {
         "model_used": active_label,
         "active_model": active_label,
-        "accuracy": _format_health_metric(metrics.get("accuracy"), default="<old fabricated default — see docs/HISTORY_FABRICATIONS.md>"),
-        "f1_score": _format_health_metric(metrics.get("f1_score", metrics.get("f1")), default="<old fabricated default — see docs/HISTORY_FABRICATIONS.md>"),
+        "accuracy": _format_health_metric(metrics.get("accuracy"), default="—"),
+        "f1_score": _format_health_metric(metrics.get("f1_score", metrics.get("f1")), default="—"),
         "device": str(artifacts.device or "cpu"),
     }
```

---

## Defect 2 — False Zero FPR Replaced with None (null in JSON)
- **File**: `backend/services/metrics_service.py`
- **Function**: `build_api_metrics_payload()`
- **Commit SHA**: `46e7b87`
- **Revert**: `git revert 46e7b87`

### Code Diff:
```diff
--- a/backend/services/metrics_service.py
+++ b/backend/services/metrics_service.py
@@ -66,7 +66,7 @@ def build_api_metrics_payload(scans: list[dict[str, Any]]) -> dict[str, Any]:
         tn_count = float(offline_raw["tn"])
         false_positive_rate = fp_count / max(1.0, fp_count + tn_count)
     else:
-        false_positive_rate = float(offline_raw.get("fpr", 0.0) or 0.0)
+        false_positive_rate = None
 
    # removed: live-qa metadata read (relocated to docs/HISTORY_FABRICATIONS.md)
@@ -109,7 +109,7 @@ def build_api_metrics_payload(scans: list[dict[str, Any]]) -> dict[str, Any]:
         "precision": precision,
         "recall": recall,
         "f1Score": f1,
-        "falsePositiveRate": false_positive_rate if false_positive_rate is not None else 0.0,
+        "falsePositiveRate": false_positive_rate,
         "accuracy_source": "offline_holdout_evaluation",
```

---

## Defect 3 (UI) — UI Render Layer Re-fabricating 0.0% from Null FPR
- **Files**:
  - `frontend/artifacts/phishshield/src/pages/dashboard.tsx`
  - `frontend/artifacts/phishshield/src/lib/metricFormatters.ts`
  - `frontend/artifacts/phishshield/src/lib/metricFormatters.test.ts`
- **Commit SHA**: `71d35c6`
- **Revert**: `git revert 71d35c6`

### Code Diff:
```diff
--- a/frontend/artifacts/phishshield/src/pages/dashboard.tsx
+++ b/frontend/artifacts/phishshield/src/pages/dashboard.tsx
@@ -2645,7 +2645,13 @@
-  const benchmarkAccuracy = Number(offlineEvaluation.accuracy ?? learningMetrics.accuracy ?? 0);
-  const benchmarkPrecision = Number(offlineEvaluation.precision ?? learningMetrics.precision ?? 0);
-  const benchmarkRecall = Number(offlineEvaluation.recall ?? learningMetrics.recall ?? 0);
-  const benchmarkF1 = Number(offlineEvaluation.f1_score ?? offlineEvaluation.f1Score ?? learningMetrics.f1Score ?? 0);
-  const benchmarkFpr = Number(
-    offlineEvaluation.false_positive_rate ?? learningMetrics.falsePositiveRate ?? 0,
-  );
+  const parseMetricNumber = (val: unknown): number | null => {
+    if (typeof val === 'number' && !Number.isNaN(val)) return val;
+    if (typeof val === 'string' && val.trim() !== '' && val.trim() !== '—') {
+      const num = Number(val);
+      return Number.isNaN(num) ? null : num;
+    }
+    return null;
+  };
+
+  const benchmarkAccuracy = parseMetricNumber(offlineEvaluation.accuracy ?? learningMetrics.accuracy);
+  const benchmarkPrecision = parseMetricNumber(offlineEvaluation.precision ?? learningMetrics.precision);
+  const benchmarkRecall = parseMetricNumber(offlineEvaluation.recall ?? learningMetrics.recall);
+  const benchmarkF1 = parseMetricNumber(offlineEvaluation.f1_score ?? offlineEvaluation.f1Score ?? learningMetrics.f1Score);
+  const benchmarkFpr = parseMetricNumber(offlineEvaluation.false_positive_rate ?? learningMetrics.falsePositiveRate);
```

### Pre-Fix Failure Output (Proof of Regression Testing for UI FPR):
```
Running formatBenchmarkFpr unit tests...
Case A (null): {"valueText":"0.0%","captionText":"(lower is better)"}
Error: Expected valueText to be '—', got '0.0%'
    at runTests (frontend/scripts/src/test_fpr_format.ts:10:11)
```

### Post-Fix Test Success Output:
```
Running metricFormatters unit tests...
Case A (null FPR): {"valueText":"—","captionText":"(not computed)"}
Case B (0.073 FPR): {"valueText":"7.3%","captionText":"(lower is better)"}
All metricFormatters tests PASSED!
```

---

## Audit of `?? 0` Usages in `dashboard.tsx`

| Category | Instances / Lines | Handled Status & Reason |
|---|---|---|
| **Backend Metrics** | Lines 2645–2651: `accuracy`, `precision`, `recall`, `f1_score`, `false_positive_rate` | **FIXED**: Replaced `?? 0` with `parseMetricNumber` (preserving `null` / `"—"` and formatting via `formatBenchmarkFpr` / `formatBenchmarkMetric`). |
| **Feedback / Agreement** | Line 2657–2660: `feedbackAgreementRate ?? 0` | **PRESERVED**: Handled via `hasFeedbackSamples ? ... : 'N/A'`. |
| **Risk Scores (0–100)** | Lines 610, 732, 1013, 2210, 2244, 2405–2416, 2586–2596, 2759, 2774 | **PRESERVED**: Numeric score arithmetic/clamping where 0 is the true integer baseline. |
| **Counters / Lengths** | Lines 1705–1707 (`phishingDetected`, `safeDetected`), 1897 (`pending_retrain`), 2652–2655 (`totalScans`, `feedbackSamples`), 2748 (`total_signals_analyzed`) | **PRESERVED**: Integral counters where 0 correctly denotes zero occurrences. |

---

## Clarity & Transparency Notes

1. **Note on `/health` Live Smoke vs Unit Testing**:
   > Live `/health` smoke does not exercise the metadata-missing path; the unit test (`test_health_endpoint_has_no_numeric_metrics_when_metadata_missing`) does via active monkeypatching.
2. **Note on CI Test Collection**:
   > 276 passed is measured with 9 files still excluded by `collect_ignore` in `tests/conftest.py`.

---

## Verification & Build Outputs

## Follow-up close-out (2026-08-29)

### Pre-fix render evidence for all benchmark metrics

The pre-fix fixture reproduced the dashboard's `Number(value ?? 0)` path with
an all-null metrics payload. `false_positive_rate` rendered `"—"` because its
separate `> 0` JSX guard was already present. `accuracy`, `precision`,
`recall`, and `f1_score` each rendered fabricated `"0.0%"`. The real-value
cases rendered `97.2%`, `94.1%`, `99.1%`, and `96.5%`, respectively. The
fixed unit test now asserts the all-null payload renders `"—"` for all five.

### Reproduction harness

`diagnostics/reproduce_headlines.py` was **rebuilt**, not restored: Git
history, the scratch tree, its evidence backup, and unreachable Git objects
contained no surviving harness source. It parses `data/training_meta.json`,
uses `csv.DictReader` for the committed CSV, reruns the exact
`backend/train_model.py` recipe in memory, and computes FPR as `FP/(FP+TN)`.
Its raw measurement was 2,000 CSV records, 1,600/400 train/test rows, 1.0
accuracy/precision/recall/F1, and FPR 0.0 from FP 0 and TN 200. Before the
metadata repair, stored metadata metrics were accuracy 0.971902595664972,
precision 0.940530058177117, recall 0.9911444141689373, and F1
0.9651741293532339; they did not match the freshly recomputed metrics.
Historical C1–C4 headlines remain
unreproducible because their runners, corpus inputs, and transformer weights
are absent; their existing JSON artifacts remain preserved evidence.

### CI wiring proof

No Vitest configuration exists. The frontend package now has `test:unit` and
`test` scripts using the existing `tsx` runtime, and CI runs
`pnpm --filter @workspace/phishshield test`. A temporary assertion expecting
`"0.0%"` failed with exit code 1; it was reverted before final verification.

### Backend Tests:
```
====================== 276 passed, 28 warnings in 38.50s ======================
```
*(276/276 passed of the collection CI actually runs).*

### Frontend Typecheck & Production Bundle Build:
```
artifacts/phishshield typecheck: Done (0 errors)
artifacts/api-server typecheck: Done (0 errors)
scripts typecheck: Done (0 errors)
artifacts/api-server build: dist\index.cjs 2.1mb (Done)
artifacts/phishshield build:
  dist/public/index.html                     1.72 kB │ gzip:   0.75 kB
  dist/public/assets/index-CZoh4ffn.css    147.48 kB │ gzip:  23.10 kB
  dist/public/assets/index-Dqyq6Kf3.js   1,011.29 kB │ gzip: 300.79 kB
✓ built in 15.89s
Exit Code: 0
```
