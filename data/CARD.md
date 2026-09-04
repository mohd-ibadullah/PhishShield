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

- Files still holding identifiers in the working tree (measured 2026-09-04, `python tools/redact_pii.py --dry-run`): 45 files, 1189 email addresses, 7 phone numbers — the two non-allowlisted datasets (`data/combined_test_dataset.json` 303 emails, `data/last_txt_dataset.json` 221 emails) plus quoted sample addresses in test/tool fixtures. No redaction executed (C5: proposal only; the decision is the operator's).
- Matching lines in git history (measured 2026-09-04: `git log -p --all -- data/combined_test_dataset.json docs/sample_emails_reference.txt`): 12 — truth lives in git history; no history rewrite (RB5).
- The 5 QA tools under `tools/` (ablate_a1.py, probe_a1_deep.py, reconcile_a1_discrepancy.py, run_neural_suite.py, verify_prompt_samples.py) carry PII on disk and in history; they are out of the index (`git rm --cached`, commit 01b356c) but not erased.
| feedback_memory.json | — | Runtime feedback memory |
| feedback_state.json | — | Feedback retrain state |
