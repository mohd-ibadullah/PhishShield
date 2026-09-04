"""C3/V31: CI --deselect list must exactly match the machine-readable gaps block
in FIX_LEDGER.md, and the product-gap-tracking job must execute the same node ids.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CI_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
LEDGER_PATH = PROJECT_ROOT / "FIX_LEDGER.md"

NODE_ID_RE = re.compile(r"(tests/[A-Za-z0-9_./-]+::[A-Za-z0-9_\[\]-]+)")
NAME_RE = re.compile(r"test_\w+")


def _ci_deselect_ids() -> set[str]:
    text = CI_PATH.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'--deselect "([^"]+)"', text))


def _ci_gap_job_ids() -> set[str]:
    text = CI_PATH.read_text(encoding="utf-8", errors="replace")
    idx = text.find("product-gap-tracking:")
    assert idx != -1, "product-gap-tracking job not found in ci.yml"
    rest = text[idx:]
    nxt = re.search(r"\n  (\w[\w-]*):\n", rest)
    section = rest[: nxt.start()] if nxt is not None else rest
    return set(NODE_ID_RE.findall(section))


def _ledger_gap_names() -> set[str]:
    text = LEDGER_PATH.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^## gaps\s*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert m is not None, "gaps block not found in FIX_LEDGER.md"
    names: set[str] = set()
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            tok = NAME_RE.search(line)
            if tok is not None:
                names.add(tok.group(0))
    return names


def _function_name(node_id: str) -> str:
    return node_id.split("::", 1)[1].split("[", 1)[0]


def test_ci_deselect_matches_ledger_gaps() -> None:
    deselect_ids = _ci_deselect_ids()
    gap_names = _ledger_gap_names()

    assert deselect_ids, "CI has no --deselect entries; gaps block would be dead"
    assert gap_names, "FIX_LEDGER.md gaps block has no entries"

    deselect_names = {_function_name(nid) for nid in deselect_ids}
    assert deselect_names == gap_names, (
        f"CI deselects {sorted(deselect_names)} but FIX_LEDGER.md gaps are "
        f"{sorted(gap_names)} — deselect list and gaps block must name the same functions"
    )

    # The product-gap-tracking job must execute exactly the deselected node ids.
    gap_job_ids = _ci_gap_job_ids()
    assert gap_job_ids == deselect_ids, (
        f"product-gap-tracking executes {sorted(gap_job_ids)} but the main job "
        f"deselects {sorted(deselect_ids)}"
    )

    # Every deselect must be a specific parameterized case, never a whole set.
    for nid in deselect_ids:
        assert "[" in nid, f"deselect {nid} hides the whole parameter set, not one case"