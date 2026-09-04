"""T10: PII guard — only allowlisted files may contain email/phone patterns."""
from __future__ import annotations

import pathlib
import re
import subprocess


def _load_allowlist() -> set[str]:
    p = pathlib.Path("data/PII_ALLOWLIST.txt")
    if not p.exists():
        return set()
    lines = p.read_text(encoding="utf-8").splitlines()
    return {line.split(":")[0].strip() for line in lines if line.strip() and not line.startswith("#")}


ALLOWLIST_ENTRY_RE = re.compile(r"^[^#][^:]+: .+$")


def test_allowlist_entries_are_machine_parsable():
    """D2/V14: every non-comment allowlist line must be `<path>: <justification>`.
    Comments are allowed only as `#` lines above the block; a line without a
    justification (no `: ` separator) must be rejected by the parser."""
    p = pathlib.Path("data/PII_ALLOWLIST.txt")
    lines = p.read_text(encoding="utf-8").splitlines()
    entries = [line for line in lines if line.strip() and not line.startswith("#")]
    assert entries, "allowlist has no entries"
    bad = [line for line in entries if not ALLOWLIST_ENTRY_RE.match(line)]
    assert not bad, f"allowlist entries missing `<path>: <justification>` form: {bad}"
    for line in entries:
        path_part, justification = line.split(":", 1)
        assert path_part.strip() == path_part, f"allowlist path has stray whitespace: {line!r}"
        assert justification.strip(), f"allowlist entry has empty justification: {line!r}"
    # Parser must reject an entry without a justification.
    assert not ALLOWLIST_ENTRY_RE.match("data/foo.csv"), "parser accepted bare path"
    assert not ALLOWLIST_ENTRY_RE.match("data/foo.csv: "), "parser accepted empty justification"


def test_no_pii_in_non_allowlisted_files():
    """Only files in PII_ALLOWLIST.txt may contain email/phone patterns.
    Redacted placeholders (user<N>@example.invalid, +9100000000XX) are excluded."""
    allowlist = _load_allowlist()
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
    email_re = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    phone_re = re.compile(r"\+91[\d\s-]{8,12}")
    violations = []
    for f in files:
        if f in allowlist:
            continue
        try:
            t = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        # Find emails, filter out redacted ones
        emails = [e for e in email_re.findall(t) if "example.invalid" not in e]
        # Find phones, filter out redacted ones (start with +9100000000)
        phones = [p for p in phone_re.findall(t) if not p.startswith("+9100000000")]
        if emails or phones:
            violations.append(f"{f}: {len(emails)} emails, {len(phones)} phones")
    assert not violations, f"PII found in non-allowlisted files: {violations}"
