# HISTORY_FABRICATIONS.md — Historical claims archive

> **These numbers were claimed and are NOT measured.** Every entry below is a
> historical quote relocated from the active docs (FINDINGS.md, FINDINGS_SUMMARY.md,
> FIX_LEDGER.md, FIX_2DEFECTS.md, W2_HARDENING_REPORT.md, PHISHSHIELD_FINAL.md,
> README.md, frontend/MASTER_GUIDE.md) during the 2026-09-04 fix pass (V12/D1).
> The active docs no longer assert any of them. Current measured values live in
> `data/training_meta.json` (metrics) and `data/CARD.md` (dataset counts).

## Claimed accuracy/F1 figures

- F07 (from FINDINGS.md): "`frontend/MASTER_GUIDE.md` claims 97.19% accuracy / 96.52% F1 but `data/training_meta.json` reports 100% accuracy / F1" — CONFIRMED, HIGH. Verification quoted: `grep "97.19" frontend/MASTER_GUIDE.md` → 4 occurrences; `data/training_meta.json` metrics → `{'accuracy': 1.0, 'precision': 1.0, 'recall': 1.0, 'f1_score': 1.0}`.
- F32 (from FINDINGS.md): "README.md accuracy section uses dynamic reference (`from training_meta.json`) — claim is traceable but values changed since 97.19% was written" — CONFIRMED, LOW. MASTER_GUIDE.md had hardcoded 97.19%; the canonical value is 1.0 (100%).
- F07 — HIGH (from FINDINGS_SUMMARY.md): "MASTER_GUIDE.md claims 97.19% accuracy in 4 locations, but training_meta.json (the canonical source per README.md) reports 100% (1.0). The discrepancy means either training_meta.json was overwritten after the claim was written, or the claim references a stale version. Both cannot be correct."
- Untraceable-numbers table (from FINDINGS_SUMMARY.md): "97.19% accuracy — MASTER_GUIDE.md:26,41,252,536 — No: contradiction with canonical source"; "96.52% F1 — MASTER_GUIDE.md:26,536 — No: same contradiction"; "live_qa range 80–85% — README.md:275 — field absent from file — No". Summary line: "Numbers with no traceable source: 3 (97.19%, 96.52%, live_qa range)".
- D8 (from FIX_LEDGER.md): "(8) Unsupported marketing claims in UI/docs": UI and overview claimed 97.4% transformer accuracy in live demo and 18,684 active training rows. Replaced with honest labels; historical disclaimer added to the system-readiness audit report.
- D12 (from FIX_LEDGER.md): "(12) README honesty and command reproducibility": README contained unverified headline numbers (97.19%, 14,947 rows, 66 passed) without reproduction commands. Replaced with dynamic references to training_meta.json.
- 51 (from FIX_LEDGER.md): "`data/training_meta.json` carried non-reproducible metadata (0.9719 / 18,684 rows / absolute path) and was overwritten by multiple writers."
- M1/D7 (from FIX_LEDGER.md / PHISHSHIELD_FINAL.md): health label hardcoded as "SecureBERT/MuRIL-GPU-97.4%" while running TF-IDF → changed to "TF-IDF Logistic Regression" in backend and Space.
- README.md (from PHISHSHIELD_FINAL.md, line 272): "README false numbers (18684, 97.4%)".
- F32 (from PHISHSHIELD_FINAL.md, line 129): "live_qa range 80-85% claim — appears in README.md:275 as 'That honest range is also stored under live_qa in data/training_meta.json' but the live_qa field does not exist in training_meta.json. The claim is UNTRACEABLE and should be removed from README.md until a live QA measurement is actually performed and stored."
- F08 (from FINDINGS.md): "`data/training_meta.json` claims `live_qa` range exists but field is absent" — CONFIRMED, MED. Verification quoted: `print('live_qa:', d.get('live_qa','NOT PRESENT'))` → `live_qa: NOT PRESENT`; `README.md:275` said "That honest range is also stored under `live_qa` in `data/training_meta.json`".
- FIX_2DEFECTS.md code-diff quotes (historical `_format_health_metric` defaults): `- "accuracy": _format_health_metric(metrics.get("accuracy"), default="98.9%")` and `- "f1_score": _format_health_metric(metrics.get("f1_score", metrics.get("f1")), default="98.6%")`; plus the removed `live_qa` metadata block (`live_qa = metadata.get("live_qa") …` / `live_range = live_qa.get("estimated_accuracy_range")`).
- W2_HARDENING_REPORT.md audit table (grep counts for the fabricated health label): "`97.4` | 0 | 2". PHISHSHIELD_FINAL.md carried the same table.
- README.md line 240: "Previous versions referenced 18,684 rows" (current committed row count is measured from `data/Phishing_Email.csv`; see `data/CARD.md`).

## Claimed dataset row counts (18,684 / 14,947 / 3,737)

- frontend/MASTER_GUIDE.md (lines 249-251, 385-387): "dataset rows: **18,684**", "train rows: **14,947**", "test rows: **3,737**" — claimed split of the training dataset. Current measured counts: `data/Phishing_Email.csv` = 2,000 records / 18,134 lines (V11), 410 collected tests (V09), training split per `data/training_meta.json`.
- README.md line 230: "`data/Phishing_Email.csv` (~18,133 rows)" — approximate line count; superseded by the exact measured record count in `data/CARD.md`.

## Outcome

All entries above were relocated here on 2026-09-04 so the active docs contain
only traceable, measured numbers. No entry here is a current claim.