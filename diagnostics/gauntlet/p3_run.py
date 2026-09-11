"""P3 dynamic model gauntlet: 6 systems x 22 cases, live inference, no static checks.

Systems: tfidf, securebert, muril, indicbert (inactive-verify: runs standalone,
never routed), ensemble, xlmr.
Cases: built at RUNTIME from repo-committed sources (transform stated per case).
Result file stores sha256 + category only (RB7) — never email content.
Verdict classes: risk>60 phish / <=25 ham / else suspicious (scan convention).
NOT a metric claim: sanity-gauntlet (agent-generated cases, small n).
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

import main  # noqa: E402
import ml2_router  # noqa: E402
from certification_run import CERT_CASES  # noqa: E402

SCAN_URL = "http://127.0.0.1:9212/scan-email"


def sha(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def load_sources():
    sys.path.insert(0, str(REPO / "tests"))
    import multilingual_test_cases as mtc

    eval_rows = {}
    for line in open(REPO / "diagnostics" / "eval_set_v1.jsonl", encoding="utf-8"):
        r = json.loads(line)
        eval_rows[r["id"]] = r
    adv = json.load(open(REPO / "data" / "adversarial_cases.json", encoding="utf-8"))
    adv_rows = {c["id"]: c for c in adv["cases"]}
    p3 = json.load(open(REPO / "diagnostics" / "gauntlet_results_p3.json", encoding="utf-8"))
    p3_rows = {r["id"]: r for r in (p3 if isinstance(p3, list) else p3.get("rows", p3.get("cases", [])))}
    hyg = open(REPO / "tests" / "test_prompt_hygiene.py", encoding="utf-8").read()
    return mtc, eval_rows, adv_rows, p3_rows, hyg


def build_cases(mtc, eval_rows, adv_rows, p3_rows, hyg):
    inj_line = [l for l in hyg.splitlines() if "ignore previous instructions" in l][0].strip().strip('"').strip("'")
    otps = "O-T-P bhejo abhi warna block"  # backend/reports/verification/elite_api_eval.json:10619
    cases = [
        ("G01", "english-phish", "PHISH", "eval_set_v1.jsonl IN-KW-01 as-is", eval_rows["IN-KW-01"]["text"]),
        ("G02", "hindi", "PHISH", "multilingual_test_cases.hindi_otp_scam as-is", mtc.HINDI_PHISHING_CASES[0]["email"]),
        ("G03", "hindi-ham", "HAM", "multilingual_test_cases.hindi_awareness_safe as-is", mtc.HINDI_PHISHING_CASES[3]["email"]),
        ("G04", "telugu", "PHISH", "multilingual_test_cases.telugu_bank_urgency as-is", mtc.TELUGU_PHISHING_CASES[1]["email"]),
        ("G05", "telugu-ham", "HAM", "multilingual_test_cases.telugu_awareness_safe as-is", mtc.TELUGU_PHISHING_CASES[2]["email"]),
        ("G06", "urdu", "PHISH", "gauntlet_results_p3.json C06 text as-committed (orig: hindi_otp_scam Devanagari->Perso-Arabic map)", p3_rows["C06"]["text"]),
        ("G07", "tamil", "PHISH", "gauntlet_results_p3.json C07 text as-committed (orig: telugu_bank_urgency Telugu->Tamil map)", p3_rows["C07"]["text"]),
        ("G08", "bengali", "PHISH", "gauntlet_results_p3.json C08 text as-committed (orig: hindi_otp_scam Devanagari->Bengali map)", p3_rows["C08"]["text"]),
        ("G09", "german", "PHISH", "gauntlet_results_p3.json C09 text as-committed (orig: CERT_CASES[0] EN->DE map)", p3_rows["C09"]["text"]),
        ("G10", "marketing-ham", "HAM", "gauntlet_results_p3.json C10 redacted text as-committed (orig chain cites combined_eval.jsonl — FILE NOT IN REPO, flagged)", p3_rows["C10"]["text"]),
        ("G11", "neutral-ham", "HAM", "gauntlet_results_p3.json C11 text as-committed (orig: CERT_CASES first safe row)", p3_rows["C11"]["text"]),
        ("G12", "homoglyph-url", "PHISH", "data/adversarial_cases.json homoglyph_bank_lure email_text as-is", adv_rows["homoglyph_bank_lure"]["email_text"]),
        ("G13", "zero-width", "PHISH", "gauntlet_results_p3.json C13 text as-committed (orig: hindi_otp_scam + U+200B every 3rd letter)", p3_rows["C13"]["text"]),
        ("G14", "base64-payload", "PHISH", "gauntlet_results_p3.json C14 text as-committed (orig: CERT_CASES[0] whole-text base64)", p3_rows["C14"]["text"]),
        ("G15", "no-spaces", "PHISH", "elite_api_eval.json 'O-T-P bhejo abhi warna block' whitespace removed: " + "".join(otps.split()), "".join(otps.split())),
        ("G16", "all-caps-urgency", "PHISH", "CERT_CASES[0][0] .upper() (deterministic)", CERT_CASES[0][0].upper()),
        ("G17", "prompt-injection", "PHISH", "test_prompt_hygiene.py:34 injection string + CERT_CASES[0] lure", inj_line + " " + CERT_CASES[0][0]),
        ("G18", "mixed-script", "PHISH", "gauntlet_results_p3.json C18 text as-committed (orig: homoglyph row + telugu_bank_urgency concat)", p3_rows["C18"]["text"]),
        ("G19", "degenerate-1char", "NONE", "single-char probe; decidable-only, no label", "x"),
        ("G20", "degenerate-empty", "NONE", "whitespace-only probe; decidable-only, no label", "   "),
        ("G21", "boilerplate-10kb", "HAM", "CERT first safe row repeated to >10KB (deterministic)", (CERT_CASES[0][0] + " ") * 120),
        ("G22", "duplicate-of-earlier", "PHISH", "byte-identical to G01; idempotence cell", eval_rows["IN-KW-01"]["text"]),
    ]
    assert cases[21][4] == cases[0][4], "G22 must equal G01 bytes"
    return cases


def sys_tfidf(t):
    v = main.artifacts.vectorizer.transform([t])
    return float(main.artifacts.model.predict_proba(v)[0][1])


def sys_securebert(t):
    return float(main._predict_provider_probability(main._securebert_provider, t))


def sys_muril(t):
    return float(main._predict_provider_probability(main._muril_provider, t))


def sys_indicbert(t):
    r = main.predict_with_indicbert(t)
    return None if r is None else float(r)


def sys_ensemble(t):
    e = main.ensemble_score(t)
    return float(e.get("score", 0.0))


def sys_xlmr(t):
    r = ml2_router._v2_predict(t)
    if r is None:
        return None
    if r["argmax"] == 1:
        return "dead_class"
    return float(r["probs"][0])


SYSTEMS = [
    ("tfidf", sys_tfidf),
    ("securebert", sys_securebert),
    ("muril", sys_muril),
    ("indicbert", sys_indicbert),
    ("ensemble", sys_ensemble),
    ("xlmr", sys_xlmr),
]


def scan_email(t):
    req = urllib.request.Request(SCAN_URL, data=json.dumps({"email_text": t}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=180))
        return {"http": 200, "risk": int(d.get("risk_score") or 0),
                "verdict": d.get("verdict"), "leg": d.get("router_leg")}
    except urllib.error.HTTPError as e:
        return {"http": e.code, "risk": None, "verdict": None, "leg": None}


def verdict_class(risk):
    if risk is None:
        return "error"
    if risk > 60:
        return "phishing"
    if risk <= 25:
        return "ham"
    return "suspicious"


EXPECTED_CLASS = {"PHISH": "phishing", "HAM": "ham"}


def main_run():
    main.load_artifacts()  # TF-IDF + IndicBERT (inactive-verify needs it loaded)
    mtc, eval_rows, adv_rows, p3_rows, hyg = load_sources()
    cases = build_cases(mtc, eval_rows, adv_rows, p3_rows, hyg)
    print(f"systems=6 cases={len(cases)} cells={6 * len(cases)}", flush=True)
    out_rows = []
    integ_ids = {"G02", "G04", "G08", "G10", "G12"}
    for cid, cat, exp, transform, text in cases:
        row = {"id": cid, "category": cat, "sha256": sha(text),
               "expected": exp, "transform": transform, "systems": {}}
        for sname, fn in SYSTEMS:
            t0 = time.perf_counter()
            try:
                s = fn(text)
                ms = int((time.perf_counter() - t0) * 1000)
                ok = isinstance(s, float) and 0.0 <= s <= 1.0
                row["systems"][sname] = {"score": round(s, 4) if ok else s, "ms": ms, "pass": ok}
            except Exception as e:
                ms = int((time.perf_counter() - t0) * 1000)
                row["systems"][sname] = {"score": None, "ms": ms, "pass": False, "error": type(e).__name__}
        if cid in integ_ids:
            t0 = time.perf_counter()
            sc = scan_email(text)
            ms = int((time.perf_counter() - t0) * 1000)
            direct_leg = {"G02": "v2_xlmr", "G04": "v2_xlmr", "G08": "v2_xlmr"}.get(cid, "ensemble")
            match = (verdict_class(sc["risk"]) == EXPECTED_CLASS.get(exp)) if exp in EXPECTED_CLASS and sc["http"] == 200 else None
            row["integration"] = {"http": sc["http"], "risk": sc["risk"], "leg": sc["leg"],
                                  "scan_class": verdict_class(sc["risk"]), "matches_expected": match, "ms": ms}
        out_rows.append(row)
        cells_pass = sum(1 for s in row["systems"].values() if s["pass"])
        print(f"{cid} {cat}: direct {cells_pass}/6" +
              (f" integ http={row['integration']['http']} class={row['integration']['scan_class']} match={row['integration']['matches_expected']}" if "integration" in row else ""),
              flush=True)
    json.dump({"note": "sanity-gauntlet (agent-generated cases, small n) - NOT a metric claim",
               "counts": {"systems": 6, "cases": len(cases), "cells": 6 * len(cases)},
               "rows": out_rows},
              open(REPO / "diagnostics" / "gauntlet_matrix.json", "w"), indent=1)
    print(f"DONE cells={6 * len(cases)} rows={len(out_rows)}")


if __name__ == "__main__":
    main_run()
