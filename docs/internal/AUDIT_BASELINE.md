# PhishShield Audit Baseline

| Metric | Value |
|--------|-------|
| Commit | c247977 |
| Tests collected | 389 |
| Test files (test_*.py) | 43 |
| scan_logs.jsonl lines | 80,240 |
| scan_logs.jsonl bytes | 40,385,999 |
| scans.db rows | 201 |
| scan_explanations rows | 287 |

## Reconciliation

389 vs 404 → 389 is correct (measured by `python -m pytest tests/ --co -q`); 404 has not happened yet — it is the expected count after tests are added in this task.

50 vs 43 test files → 43 is correct (measured by `ls tests/test_*.py | wc -l`); the audit's 50 counted non-test_*.py files under tests/.
