"""Load derived paper evidence only while its result provenance still matches.

AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""

import hashlib
import json
from pathlib import Path


def load_analysis(root: Path) -> dict:
    analysis = json.loads(
        (root / "paper/data/analysis.json").read_text(encoding="utf-8")
    )
    hashes = analysis.get("hashes", {})
    if not hashes:
        raise ValueError("Missing paper provenance; rerun scripts/analyze_paper.py")
    for relative, expected in hashes.items():
        source = root / "results" / relative
        if (
            not source.is_file()
            or hashlib.sha256(source.read_bytes()).hexdigest() != expected
        ):
            raise ValueError(
                f"Stale paper analysis: {relative}; rerun scripts/analyze_paper.py"
            )
    diagnostics = analysis.get("diagnostic_hashes")
    if not diagnostics:
        raise ValueError(
            "Missing diagnostic provenance; rerun scripts/analyze_paper.py"
        )
    for relative, expected in diagnostics.items():
        source = root / "paper/data" / relative
        if (
            not source.is_file()
            or hashlib.sha256(source.read_bytes()).hexdigest() != expected
        ):
            raise ValueError(
                f"Stale paper diagnostic: {relative}; rerun scripts/analyze_paper.py"
            )
    return analysis
