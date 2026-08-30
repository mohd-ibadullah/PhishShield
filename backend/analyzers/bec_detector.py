"""Deterministic no-link BEC detection."""

from __future__ import annotations

from perf_timing import timed


@timed("detect_bec")
def evaluate_bec_no_link(
    email_text: str,
    *,
    linked_domains: list[str],
    action_money_requested: bool,
    behavior_urgency: bool,
    behavior_secrecy: bool,
) -> tuple[bool, str]:
    """Evaluate the no-link BEC (business email compromise) contract.

    Returns (True, reason) only when the message requests money/action,
    shows urgency or secrecy pressure, and contains no linked domains —
    the classic CEO-fraud / vendor-payment-switch shape. Any linked domain
    moves the message out of the no-link BEC contract.
    """
    if linked_domains:
        return False, "Linked domains present — outside the no-link BEC contract"
    if action_money_requested and (behavior_urgency or behavior_secrecy):
        return True, "BEC no-link pattern: money/action request with urgency or secrecy and no links"
    return False, "No-link BEC contract not satisfied"
