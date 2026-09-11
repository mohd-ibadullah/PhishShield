# ML2 Model Artifacts — measured registry (2026-09-11, ROUTER pass R0/R1; gauntlet P0.2 extends 2026-09-11)

## model_merged (V2 XLM-RoBERTa)

- path: `model_merged/` (gitignored, `.gitignore:23`)
- weights: `model.safetensors`, 1,112,208,060 bytes (1.1 GB)
- **sha256: `2e3a05d5cb82ac58123d28e86034a90375488a299d157057b2e0c9b1d8a0df30`**
- config: `XLMRobertaForSequenceClassification`, hidden 768, 12 layers, vocab 250002, transformers 5.0.0
- config `id2label`: `{"0": "LABEL_0", "1": "LABEL_1", "2": "LABEL_2"}` (generic placeholders — see label_map.json for the operative mapping)

## Measured behavior (live inference, counted in-session)

- 60-case probe + 19-case follow-up + 24-case gauntlet-1 + 30-case gauntlet-2 = **133 live predictions**
- `LABEL_1` argmax wins: **0 of 133**. Max LABEL_1 probability ever observed: **0.0001**.
- => `label1_unreachable: true` — the marketing class head never fires in this artifact.
- Operative mapping (owner decision 2026-09-11, probe-backed): `0=phishing`, `2=ham`, `1=unresolved_dead`.
- Marketing detection stays on TF-IDF+LogReg + rules (gauntlet: 0/4 marketing false alarms, 1 ms latency).

## Slot changes (shootout evidence, 2 rounds)

- non-Latin (hi/te/ur/ta/bn): **V2 XLM-R replaces IndicBERT** (IndicBERT ranked last in both rounds;
  XLM-R 6/6 non-Latin recall in round 1).
- English: existing ensemble (SecureBERT + MuRIL + anchor) unchanged — gauntlet round 2: 18/18 phish, 8/8 ham.
- Hinglish/code-mixed: MuRIL.
- TF-IDF+LogReg: fast marketing/ham pre-filter, kept.

## Deployed-model limits (owner decision A, 2026-09-12)

Classic scams strong; LLM-generated/BEC weak — partial rule mitigation only, no modern-coverage claim.

- Spam class (LABEL_1) is dead in the deployed `model_merged` artifact: p1 = 0.0000 on every live probe
  (20+ observations incl. diagnostics/gauntlet/v2_eval_artifacts/live_retest.py). The zip's training-era
  `evaluation_results.json` shows spam recall 0.9501 on id_test — the deployed checkpoint does not
  reproduce it. Claims stay binary (phishing-vs-rest) per label_map.json.
- Modern-attack weakness is measured, not assumed: cross_source_ood phishing recall 0.0,
  curated_modern_dark macro-F1 0.1836 (zip eval), plus 2/2 live misses on LLM-style and BEC-style
  probes (2026-09-12 retest). Router rule-layer carries BEC/modern patterns as score boosts
  (BEC_TRANSFER/CONFIDENTIAL/PAYROLL patterns, 2026-09-12) — mitigation, not detection.
- The v2 pipeline's later-stage outputs (eval_summary beyond the zip, ONNX latency, modern-corpus
  retrain) were cancelled by owner decision A (2026-09-12); research items stay in ml2/DEFERRED.md.
- New V2 model rejected verbatim (owner, 2026-09-12): `rejected: dead spam class + OOD recall 0` —
  the candidate checkpoint's spam class is unreachable (LABEL_1 never argmax in 133 live predictions)
  and cross_source_ood phishing recall measures 0.0 (evaluation_results.json), so it cannot serve as
  the non-Latin specialist. Evidence: diagnostics/gauntlet/v2_eval_artifacts/evaluation_results.json.

## Full artifact sha256 registry (gauntlet P0.2, measured 2026-09-11)

| path | bytes | sha256 | loaded-by |
|:---|---:|:---|:---|
| `model_merged/model.safetensors` | 1,112,208,060 | `2e3a05d5cb82ac58123d28e86034a90375488a299d157057b2e0c9b1d8a0df30` | `backend/ml2_router.py` (V2 non-Latin leg) |
| `backend/models/securebert_model/model.safetensors` | 498,612,824 | `bef2aa8a788efb3134ed821a495087a8a96a25b8e20891599da2cdea1a7f722d` | `backend/models/securebert_provider.py` (EN ensemble) |
| `backend/models/muril_model/model.safetensors` | 950,254,592 | `1ed4638adc0b8c7a52f44fb6c5b348ca5a8504d6fbf2904e8f8143dfe4f36eb5` | `backend/models/muril_provider.py` (EN ensemble + MX leg) |
| `backend/indicbert_model/model.safetensors` | 133,783,952 | `c51c0d684a0377d8edf180680c472355f0dbe15153f97deeea4fa960c477828f` | present-but-inactive (out of the hot path since ROUTER pass) |
| `backend/model.pkl` | 22,059 | `433d162f7f3477ed0ae597c4ba824d8c6eeb4d069fe2d8c45b88de67aab494b0` | `backend/main.py` (TF-IDF LogReg + marketing pre-filter) |
| `backend/vectorizer.pkl` | 107,193 | `373bfc706ca8fbcbed05bd3f0c534737f480e283b4f79755d55585ae66cba07e` | `backend/main.py` (TF-IDF vectorizer) |
