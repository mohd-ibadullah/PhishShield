"""§2.3: Adversarial test for short-email HMAC recovery.

xfail(strict=True): with a known key, short-email digests are recoverable
by design. If this ever passes unexpectedly, the adversarial assumption
changed — that is what strict means.

Reusable probe: scripts/adversarial_digest_probe.py --key <key>
"""
from __future__ import annotations

import hashlib
import hmac
import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from conftest import app, BACKEND_DIR

import importlib
_main = importlib.import_module("main")


def _hmac_digest(text: str) -> str:
    """Compute the same HMAC the writer uses."""
    return hmac.new(
        _main._get_preview_hmac_key(),
        text.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]


# 500 realistic one-line short emails
SHORT_EMAILS = [
    "Hi", "Hello", "Thanks", "OK", "Yes", "No", "Please help", "Urgent",
    "Call me", "Check this", "Subject: Test", "Subject: Hello",
    "Subject: Urgent", "Subject: Invoice", "Subject: Password reset",
    "Subject: Account verification", "Subject: Your OTP is 123456",
    "Subject: Meeting tomorrow", "Subject: Project update",
    "Subject: Action required", "Verify your account now",
    "Click here to claim your prize", "Your account will be suspended",
    "Send OTP immediately", "Wire transfer requested", "Invoice attached",
    "Password expires today", "Login alert from new device",
    "Your subscription expires", "Confirm your email address",
]
while len(SHORT_EMAILS) < 500:
    SHORT_EMAILS.append(f"Subject: Message #{len(SHORT_EMAILS)}")


@pytest.mark.xfail(
    strict=True,
    reason="Known test key makes short-email digests recoverable by design; "
           "if this passes unexpectedly, the adversarial assumption changed",
)
@pytest.mark.asyncio
async def test_short_email_digests_not_in_candidate_set(tmp_path) -> None:
    """With a known HMAC key, short-email digests ARE recoverable.
    This test fails (xfail) to document the finding.
    Strict=True: if it ever PASSES, that means the key changed or
    the adversarial assumption broke — the suite must fail."""
    import backend.main as bm
    bm.SCANS_DB_PATH = tmp_path / "scans-adversarial.db"
    bm.ensure_scans_db()

    test_emails = SHORT_EMAILS[:5]
    candidate_digests = {_hmac_digest(e): e for e in SHORT_EMAILS}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/session")
        for email in test_emails:
            resp = await client.post("/scan-email", json={"email_text": email})
            assert resp.status_code == 200, f"Scan failed for {email!r}: {resp.text}"

    stored_digests = []
    for record in app.state.scan_explanations.values():
        d = record.get("email_sha256", "")
        if d:
            stored_digests.append(d)

    assert len(stored_digests) == len(test_emails)

    matches = sum(1 for d in stored_digests if d in candidate_digests)
    assert matches == 0, (
        f"SHORT EMAIL ATTACK: {matches}/{len(stored_digests)} stored HMAC digests "
        f"matched candidate digests. Known key → short emails recoverable."
    )
