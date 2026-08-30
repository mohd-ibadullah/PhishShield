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

## Committed-dataset FPR caveat

Computed by `python diagnostics/reproduce_headlines.py` (the masking rule lives
in that harness only) and committed as `diagnostics/headlines_output.json`:
the 2,000-row committed set (`data/Phishing_Email.csv`) contains 1,115 template
families with 0 families shared between classes, so a random holdout split
never has to generalize across a near-duplicate template boundary. Its
measured 0.0% FPR (FP 0 / TN 200) is therefore **not** a generalization
measurement — treat it only as a same-distribution sanity check, not as
evidence of real-world false-positive behavior. An earlier revision of this
note stated 319 families; that figure could not be reproduced from committed
inputs and was replaced by the harness-computed 1,115. The backend serves
these counts to the dashboard only while `headlines_output.json` is present;
`tests/test_benchmark_caveat.py` fails if the JSON is hand-edited.

## Currently unreproducible headlines

The historical C1/C2/C3/C4 results cannot be reproduced from committed inputs:
their former runners were absent from Git history, the scratch tree, and its
evidence backup. The C1 corpus and transformer weights are not committed; C4
also lacks the required `model.safetensors` files. Surviving JSON is retained
as evidence, not treated as regenerated measurement.
