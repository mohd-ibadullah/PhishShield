# Dataset Card: Phishing_Email.csv

- **Source:** Kaggle Phishing Email Dataset
- **Licence:** CC0 (public domain) — dataset authors' declaration
- **Retrieval date:** 2026-05 (original import)
- **Row count:** 2000 (measured: `python -c "import csv;print(sum(1 for _ in csv.reader(open('data/Phishing_Email.csv')))-1)"`)
- **Label provenance:** Labels as published by the dataset authors; not independently audited
- **Note:** 601/2000 rows carry ≥2026 dates (measured: `python -c "import re,pathlib;print(sum(1 for l in pathlib.Path('data/Phishing_Email.csv').open(encoding='utf-8',errors='replace') if re.search(r'(?<!\d)(?:202[6-9]|20[3-9]\d)(?!\d)',l)))"`)

## Files in this directory

| File | Rows | Description |
|------|------|-------------|
| Phishing_Email.csv | 2000 | Main training/evaluation dataset |
| training_meta.json | — | Training metadata (accuracy, precision, recall, F1) |

## Limits

- Git history of `data/combined_test_dataset.json` and `docs/sample_emails_reference.txt` still contains +91 phone and IP-address content (V54: 12 lines measured 2026-09-04) — truth lives in git history, outside the current tree; the current tree is clean per the PII guard.
| feedback_memory.json | — | Runtime feedback memory |
| feedback_state.json | — | Feedback retrain state |
