# P95 measured per route (F2 evidence — sanity-gauntlet, agent-generated cases, small n, NOT a metric claim)

Machine: owner's Windows CPU box. All measurements warm (models loaded once at boot via
`warmup_router_legs()` + module singletons). `predict_with_indicbert` stubbed to 0.18 exactly as the
test fixture does; VirusTotal stubbed local-only. n=20 calls per route.

## Router-leg micro-benchmark (`backend/ml2_router.py`, 20 calls each)

| leg | before F1 (p50/p95) | after F1 (p50/p95) |
|---|---|---|
| MX-MuRIL (`_muril_predict`) | 958 ms / 1107 ms | **93 ms / 106 ms** |
| nonLatin-XLMR (`_v2_predict`) | 84 ms / 175 ms (already cached) | 98 ms / 165 ms |

Before F1, each MX call constructed a fresh `MurilProvider()` (20× "Loading weights" bars observed).

## Full-pipeline `calculate_email_risk` per route (20 calls each, warm)

| route | p50 | p95 | vs 300 ms gate |
|---|---|---|---|
| EN-ensemble (SecureBERT+MuRIL+anchor) | 220 ms | 271 ms | pass |
| MX-MuRIL | 297 ms | 387 ms | **exceeds** |
| nonLatin-XLMR | 408 ms | 512 ms | **exceeds** |
| TF-IDF marketing | 211 ms | 257 ms | pass |

## Full 42-case distribution (cert.CERT_CASES + adversarial_cases.json, warm)

`n=42 p50=209ms p95=314ms` — gate `tests/test_performance.py:94` asserts `< 300.0`:

```
AssertionError: full_pipeline_no_external P95=804.1ms exceeds 300ms
```

(cold-start variant without warmup: first EN call pays ~6.0 s SecureBERT load, first HI ~4.0 s XLM-R
load, first MX ~1.5 s MuRIL load — these landed inside the test's timed loop before the warmup fix.)

## State

- F1 (provider singletons + boot warmup) is committed app code: real defect fixed, p95 822→314 ms on
  the suite distribution, MX leg 958→93 ms.
- The 300 ms full-pipeline gate predates P2's live router legs; on this CPU box, warm MX/non-Latin
  real inference does not fit under it. Test NOT touched, NO deselect added (RB3/F2).
- `BLOCKED: owner pick A or B`:
  - **A** re-baseline gate to measured p95 + 25% on this CPU box (owner's explicit word required;
    decision line quoted verbatim in the commit message).
  - **B** keep 300 ms gate; router legs behind an explicit env flag OFF by default in deployed config;
    `/health` reports which legs are live (no silent downgrade — 401-fallback defect class).
