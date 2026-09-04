# LIVE_TEST_PLAN.md

Source of truth for each row: the endpoint/store it reads or writes, action, and an observable pass criterion (status code / store delta / DOM text change).

| id | element | real data source (endpoint/store) | action | pass criterion |
|---|---|---|---|---|
| L001 | / button: Privacy on | see action | toggle -> privacy state flips; redaction applied on next export | see action col |
| L002 | / button: Analyze | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L003 | / button: Dashboard | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L004 | / button: Scenario Lab | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L005 | / button: Live Paste | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L006 | / button: Upload File | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L007 | / textarea: Email content to scan | see action | type a value -> scan call fires or clear works; empty submit -> validation message, no crash | see action col |
| L008 | / button: Advanced (Headers) | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L009 | / button: Clear draft | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L010 | / button: Scan Email | see action | POST /scan-email via proxy 200; result panel changes; store row +1 | see action col |
| L011 | / button: Privacy on | see action | toggle -> privacy state flips; redaction applied on next export | see action col |
| L012 | / button: Analyze | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L013 | / button: Dashboard | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L014 | / button: Retrain Now | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L015 | / button: Privacy on | see action | toggle -> privacy state flips; redaction applied on next export | see action col |
| L016 | / button: Analyze | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L017 | / button: Dashboard | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L018 | / button: Scenario Lab | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L019 | / button: Live Paste | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L020 | / button: Upload File | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L021 | / textarea: Email content to scan | see action | type a value -> scan call fires or clear works; empty submit -> validation message, no crash | see action col |
| L022 | / button: Advanced (Headers) | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L023 | / button: Clear draft | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L024 | / button: Scan Email | see action | POST /scan-email via proxy 200; result panel changes; store row +1 | see action col |
| L025 | / button: Privacy on | see action | toggle -> privacy state flips; redaction applied on next export | see action col |
| L026 | / button: Analyze | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L027 | / button: Dashboard | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L028 | / button: Scenario Lab | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L029 | / button: Live Paste | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L030 | / button: Upload File | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L031 | / button: Open Scenario Library | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L032 | / button: HDFC Bank Security <user1@example.invalid> 10:45 A | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L033 | / button: Netflix Billing <user3@example.invalid> 09:12 AM Y | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L034 | / button: SBI Security Alert <user4@example.invalid> Yesterd | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L035 | / button: Amazon Rewards <user5@example.invalid> Yesterday E | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L036 | / button: Google Security <user6@example.invalid> 2 Mar Secu | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L037 | / button: CFO Office <user7@example.invalid> Today Confident | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L038 | / button: Advanced (Headers) | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L039 | / button: Clear draft | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L040 | / button: Scan Email | see action | POST /scan-email via proxy 200; result panel changes; store row +1 | see action col |
| L041 | / button: Privacy on | see action | toggle -> privacy state flips; redaction applied on next export | see action col |
| L042 | / button: Analyze | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L043 | / button: Dashboard | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L044 | / button: Scenario Lab | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L045 | / button: Live Paste | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L046 | / button: Upload File | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L047 | / textarea: Email content to scan | see action | type a value -> scan call fires or clear works; empty submit -> validation message, no crash | see action col |
| L048 | / button: Advanced (Headers) | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L049 | / button: Clear draft | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L050 | / button: Scan Email | see action | POST /scan-email via proxy 200; result panel changes; store row +1 | see action col |
| L051 | / button: Privacy on | see action | toggle -> privacy state flips; redaction applied on next export | see action col |
| L052 | / button: Analyze | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L053 | / button: Dashboard | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L054 | / button: Scenario Lab | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L055 | / button: Live Paste | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L056 | / button: Upload File | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L057 | / textarea: Email content to scan | see action | type a value -> scan call fires or clear works; empty submit -> validation message, no crash | see action col |
| L058 | / button: Advanced (Headers) | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L059 | / textarea: Optional raw email headers | see action | type a value -> scan call fires or clear works; empty submit -> validation message, no crash | see action col |
| L060 | / button: Clear draft | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L061 | / button: Scan Email | see action | POST /scan-email via proxy 200; result panel changes; store row +1 | see action col |
| L062 | / button: Privacy on | see action | toggle -> privacy state flips; redaction applied on next export | see action col |
| L063 | / button: Analyze | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L064 | / button: Dashboard | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L065 | / button: Retrain Now | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L066 | / button: Privacy on | see action | toggle -> privacy state flips; redaction applied on next export | see action col |
| L067 | / button: Analyze | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L068 | / button: Dashboard | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L069 | / button: Scenario Lab | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L070 | / button: Live Paste | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L071 | / button: Upload File | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L072 | / textarea: Email content to scan | see action | type a value -> scan call fires or clear works; empty submit -> validation message, no crash | see action col |
| L073 | / button: Advanced (Headers) | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L074 | / button: Clear draft | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L075 | / button: Scan Email | see action | POST /scan-email via proxy 200; result panel changes; store row +1 | see action col |
| L076 | / button: Privacy off | see action | toggle -> privacy state flips; redaction applied on next export | see action col |
| L077 | / button: Analyze | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L078 | / button: Dashboard | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L079 | / button: Scenario Lab | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L080 | / button: Live Paste | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L081 | / button: Upload File | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L082 | / textarea: Email content to scan | see action | type a value -> scan call fires or clear works; empty submit -> validation message, no crash | see action col |
| L083 | / button: Advanced (Headers) | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L084 | / button: Clear draft | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L085 | / button: Scan Email | see action | POST /scan-email via proxy 200; result panel changes; store row +1 | see action col |
| L086 | /premium button: Scan now | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L087 | /premium button: Reset view | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L088 | /premium button: CFO Office Demo Release this confidential vendor t | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L089 | /premium button: HDFC Security Demo Your account will be suspended  | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L090 | /premium button: Google Security Demo Security alert for your accou | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L091 | /premium textarea: - | see action | type a value -> scan call fires or clear works; empty submit -> validation message, no crash | see action col |
| L092 | /premium button: Analyze Email | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L093 | /premium button: Dismiss | see action | click -> DOM/state change or request logged (network entry captured) | see action col |
| L094 | /premium button: Clear | see action | click -> DOM/state change or request logged (network entry captured) | see action col |

SUSPECT: rows whose behavior cannot be tied to a live data source at plan time are marked in READINESS as SUSPECT-hardcoded and become required tests.
