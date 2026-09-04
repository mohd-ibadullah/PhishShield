#!/usr/bin/env python3
"""T10: Redact PII from tracked files.

Usage:
    python tools/redact_pii.py --dry-run    # report only
    python tools/redact_pii.py              # actually redact
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+91[\d\s-]{8,12}")
IP_RE = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")

# TEST-NET-3 for IPs
TEST_NET_COUNTER = [0]


def redact_email(match: re.Match) -> str:
    return f"user{TEST_NET_COUNTER[0] % 10000}@example.invalid"


def redact_phone(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return f"+9100000000{digits[-2:]}" if len(digits) >= 10 else "+910000000000"


def redact_ip(match: re.Match) -> str:
    TEST_NET_COUNTER[0] += 1
    return f"203.0.113.{TEST_NET_COUNTER[0] % 255}"


def load_allowlist() -> set[str]:
    p = Path("data/PII_ALLOWLIST.txt")
    if not p.exists():
        return set()
    return {l.split(":")[0].strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")}


def process_file(path: Path, dry_run: bool) -> tuple[int, int]:
    """Returns (email_count, phone_count) of PII found."""
    content = path.read_text(encoding="utf-8", errors="replace")
    emails = len(EMAIL_RE.findall(content))
    phones = len(PHONE_RE.findall(content))
    if emails + phones == 0:
        return (0, 0)
    if dry_run:
        return (emails, phones)
    # Redact
    TEST_NET_COUNTER[0] = 0
    new_content = EMAIL_RE.sub(redact_email, content)
    new_content = PHONE_RE.sub(redact_phone, new_content)
    path.write_text(new_content, encoding="utf-8")
    return (emails, phones)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    allowlist = load_allowlist()
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()

    total_emails = 0
    total_phones = 0
    files_redacted = 0

    for f in files:
        if f in allowlist:
            continue
        p = Path(f)
        if not p.exists() or not p.is_file():
            # submodule gitlinks and directories are not files to redact
            continue
        emails, phones = process_file(p, args.dry_run)
        if emails + phones > 0:
            total_emails += emails
            total_phones += phones
            files_redacted += 1
            action = "WOULD REDACT" if args.dry_run else "REDACTED"
            print(f"  {action}: {f} ({emails} emails, {phones} phones)")

    print(f"\nTotal: {files_redacted} files, {total_emails} emails, {total_phones} phones")
    if args.dry_run:
        print("DRY RUN — no files modified")
    else:
        print("Redaction complete")


if __name__ == "__main__":
    main()
