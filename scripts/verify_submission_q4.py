# 本程序及代码是在人工智能工具辅助下完成的。
# Tool: ChatGPT/Codex; model: GPT-6 Astra (gpt-6-astra); developer: OpenAI.
# Model release: 2026-09-03, https://developers.openai.com/api/docs/changelog
# This declaration covers this entry point and its imported src modules.
"""Read-only fixed-Q3 Q4 replay check; does not modify frozen results.

This is a separate numerical comparison, not a replacement for or claim of
success of src.validation.validate_results. Frozen discrete fields and JSON
structure must match exactly; declared continuous fields allow abs error 1e-9.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

TOLERANCE = 1e-9
JSON_FILES = (
    "Q4_preference_frontier.json", "Q4_policy_audit.json",
    "Q4_enumeration_certificate.json", "Q4_source_manifest.json",
)
CSV_FLOAT_COLUMNS = {
    "Q4_partition_config.csv": {"工作量_s", "联合能耗_kWh"},
    "Q4_resource_summary.csv": set(),
    "Q4_preference_comparison.csv": {"transport_gini", "spatial_box_min", "energy_kwh"},
    "Q4_balanced_groups.csv": {"transport_work_s", "relay_work_s", "spatial_box_min", "energy_kwh"},
    "Q4_balanced_resources.csv": set(),
    "Q4_gap_decomposition.csv": set(),
}


def fingerprints(paths: list[Path]) -> dict[str, str]:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in paths for p in sorted(folder.rglob("*")) if p.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--q3-dir", type=Path, required=True)
    parser.add_argument("--q4-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_dirs = [args.q3_dir.resolve(), args.q4_dir.resolve()]
    output = args.output.resolve()
    if any(output.is_relative_to(p) for p in source_dirs):
        parser.error("Report output must be outside frozen Q3/Q4 directories")
    sys.path.insert(0, str(args.project_root.resolve()))
    from src.q4.partition import solve_partitions

    before = fingerprints(source_dirs)
    differences, failures, summaries = [], [], {}
    discrete_checked = 0
    float_checked = 0

    def check_float(a: float, b: float, path: str) -> None:
        nonlocal float_checked
        float_checked += 1
        error = abs(a - b)
        if not math.isfinite(a) or not math.isfinite(b):
            failures.append({"path": path, "reason": "nonfinite", "frozen": a, "recomputed": b})
        elif a != b:
            row = {"path": path, "kind": "continuous", "frozen": a, "recomputed": b,
                   "abs_error": error, "within_tolerance": error <= TOLERANCE}
            differences.append(row)
            if error > TOLERANCE:
                failures.append(row)

    def exact(a, b, path: str) -> None:
        nonlocal discrete_checked
        discrete_checked += 1
        if type(a) is not type(b) or a != b:
            failures.append({"path": path, "reason": "exact_mismatch", "frozen": a, "recomputed": b})

    def compare_json(a, b, path: str) -> None:
        if type(a) is not type(b):
            exact(a, b, path)
        elif isinstance(a, dict):
            exact(sorted(a), sorted(b), path + "/keys")
            for key in a.keys() & b.keys():
                compare_json(a[key], b[key], path + "/" + str(key))
        elif isinstance(a, list):
            exact(len(a), len(b), path + "/length")
            for index, (left, right) in enumerate(zip(a, b)):
                compare_json(left, right, path + f"/{index}")
        elif isinstance(a, float):
            check_float(a, b, path)
        else:
            exact(a, b, path)

    with tempfile.TemporaryDirectory(prefix="fixed-q4-independent-") as folder:
        stage = Path(folder)
        solve_partitions(args.q3_dir, stage, args.raw_root)
        for name in JSON_FILES:
            original = json.loads((args.q4_dir / name).read_text(encoding="utf-8"))
            replayed = json.loads((stage / name).read_text(encoding="utf-8"))
            d0, f0 = len(differences), len(failures)
            compare_json(original, replayed, name)
            summaries[name] = {"raw_exact_equal": original == replayed,
                               "continuous_differences": len(differences) - d0,
                               "failed_comparisons": len(failures) - f0}
        for name, float_columns in CSV_FLOAT_COLUMNS.items():
            with (args.q4_dir / name).open(encoding="utf-8-sig", newline="") as stream:
                original = list(csv.DictReader(stream))
            with (stage / name).open(encoding="utf-8-sig", newline="") as stream:
                replayed = list(csv.DictReader(stream))
            d0, f0 = len(differences), len(failures)
            exact(len(original), len(replayed), name + "/rows")
            for index, (left, right) in enumerate(zip(original, replayed)):
                exact(list(left), list(right), name + f"/{index}/columns")
                for key in left.keys() & right.keys():
                    path = name + f"/{index}/" + key
                    if key in float_columns:
                        check_float(float(left[key]), float(right[key]), path)
                    else:
                        exact(left[key], right[key], path)
            summaries[name] = {"rows": len(original), "raw_exact_equal": original == replayed,
                               "continuous_differences": len(differences) - d0,
                               "failed_comparisons": len(failures) - f0}
    after = fingerprints(source_dirs)
    if before != after:
        failures.append({"reason": "frozen_source_files_changed"})
    report = {
        "status": "PASS" if not failures else "FAIL",
        "scope": "Independent deterministic Q4 replay of frozen Q3; no Q1-Q3 optimization or radio replay",
        "not_a_claim_that_original_validate_results_passed": True,
        "absolute_float_tolerance": TOLERANCE,
        "discrete_policy": "Exact values/types/structure/order; CSV integer and identifier columns never tolerance-compared",
        "frozen_sources_unchanged": before == after,
        "discrete_or_structural_comparisons": discrete_checked,
        "continuous_comparisons": float_checked,
        "maximum_absolute_error": max((row["abs_error"] for row in differences), default=0),
        "files": summaries, "differences": differences, "failures": failures,
        "frozen_source_sha256": before,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "frozen_sources_unchanged", "maximum_absolute_error",
                                                  "discrete_or_structural_comparisons", "continuous_comparisons")}, ensure_ascii=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
