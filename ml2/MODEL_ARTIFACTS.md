# ML2 Model Artifacts — measured registry (2026-09-11, ROUTER pass R0/R1)

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
