# ML2 Paper Phase — DEFERRED (not skipped)

Owner-scoped: ROUTER pass (2026-09-11) shipped routing-not-fusion with the
models already in the repo. The items below need paper-grade protocol
(human labels, calibration sets, ablations) and are deferred until that
protocol exists. Each is one line + its unblock condition.

- Temperature scaling of specialist scores: DEFERRED — unblocked by a held-out
  labeled calibration set (none committed; eval slices are sanity-only).
- OOD/energy-based abstention protocol: DEFERRED — unblocked by an OOD
  evaluation set with a fixed scoring protocol.
- Abstain-threshold tuning (per-leg 0.50 is a shipped default, not tuned):
  DEFERRED — unblocked by the calibration set above; see ml2/ROUTER.yaml
  threshold_justification fields for current provenance.
- Ablation tables (EN ensemble internals, rule-layer contributions):
  DEFERRED — unblocked by a frozen eval harness + committed eval corpus.
- Inter-rater κ on a human-labeled set: DEFERRED — unblocked by a human
  labeling round with adjudication protocol.
- MuRIL-alone for EN (gauntlet n=8 ham direction, not a verdict):
  DEFERRED — paper-phase candidate, not this pass (see ml2/MODEL_ARTIFACTS.md).

Operative mapping reminder: binary PHISH/HAM (0=phishing, 2=ham,
1=unresolved_dead, never argmax in 133 live predictions). Marketing stays on
TF-IDF + rules. See ml2/label_map.json (owner decision 2026-09-11).
