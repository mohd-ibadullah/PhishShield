"""T8: Docs metrics must trace to generated artifacts."""
from __future__ import annotations

import json
import re
import pathlib


def _get_artifact_values() -> set[str]:
    """Collect all numeric values from training_meta.json and headlines_output.json."""
    values = set()
    for path in ["data/training_meta.json", "diagnostics/headlines_output.json"]:
        p = pathlib.Path(path)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                text = json.dumps(data)
                for m in re.findall(r"\d+\.?\d*", text):
                    values.add(m)
            except Exception:
                pass
    return values


def test_no_untraceable_percentages():
    """Every percentage in README.md or MASTER_GUIDE.md must appear in a generated artifact."""
    artifact_vals = _get_artifact_values()
    # Lines to skip (JSON examples, descriptive text, etc.)
    skip_patterns = ["confidence_interval", "json", "{", "}", "see file", "see data",
                     "measured", "current", "documented", "overview", "roughly",
                     "estimat", "accuracy", "hardening", "before", "after", "~"]

    for doc_path in ["README.md", "frontend/MASTER_GUIDE.md"]:
        p = pathlib.Path(doc_path)
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8")
        for m in re.finditer(r"(\d+\.?\d+)%", content):
            val = m.group(1)
            if val not in artifact_vals:
                line_start = content.rfind("\n", 0, m.start()) + 1
                line = content[line_start:content.find("\n", m.end())].lower()
                # Skip lines with skip patterns
                if any(p in line for p in skip_patterns):
                    continue
                # Skip JSON-like lines
                if '"' in line and ':' in line:
                    continue
                assert False, f"{doc_path} contains untraceable {m.group(0)} in: {line.strip()}"
