# Reproduction diagnostics

Run from the repository root:

```powershell
python diagnostics/reproduce_headlines.py
```

The command parses `data/training_meta.json`, counts the committed CSV with
`csv.DictReader`, reads `eval_set_v1.jsonl`, and reruns the exact in-memory
recipe in `backend/train_model.py`. It never writes model artifacts.

| Claim | Command | Measured value |
|---|---|---|
| Committed training rows | `python diagnostics/reproduce_headlines.py` | `csv_records` in raw output |
| Holdout accuracy / precision / recall / F1 | `python diagnostics/reproduce_headlines.py` | `measured` in raw output |
| False-positive rate | `python diagnostics/reproduce_headlines.py` | `fp / (fp + tn)` with both counts printed |
| Evaluation-set record count | `python diagnostics/reproduce_headlines.py` | `eval_set_v1_records` in raw output |

## Currently unreproducible headlines

The historical C1/C2/C3/C4 results cannot be reproduced from committed inputs:
their former runners were absent from Git history, the scratch tree, and its
evidence backup. The C1 corpus and transformer weights are not committed; C4
also lacks the required `model.safetensors` files. Surviving JSON is retained
as evidence, not treated as regenerated measurement.
