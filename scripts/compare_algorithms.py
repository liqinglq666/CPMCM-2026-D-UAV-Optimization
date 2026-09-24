"""Compare validated, actually recomputed algorithm generations (seconds, kWh).

Blank cells are not applicable, not an invented zero. Q1 has no scheduled
makespan/deadlines. Q2 has no radio requirement. Q4 copies finalized Q3 times
and sizes independent resources; repeated relay sorties are counted per group.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import PROJECT_ROOT
from src.core.io import read_csv, write_csv

FIELDS = (
    "Question",
    "Version",
    "Trips",
    "Weighted tardiness",
    "Makespan",
    "Transport energy",
    "Relay sorties",
    "Relay energy",
    "Joint energy",
    "Hard deadline violations",
    "Communication violations",
    "Communication sampling grids (s)",
    "Communication violations 0.5 s",
    "Runtime",
    "Resource shortage",
)


def rows_for(directory, version, runtimes):
    validation = json.loads((directory / "validation.json").read_text(encoding="utf-8"))
    q1, q2, q3 = (
        json.loads((directory / f"q{i}/Q{i}_metrics.json").read_text(encoding="utf-8"))
        for i in (1, 2, 3)
    )
    output = []

    def add(question, **values):
        row = dict.fromkeys(FIELDS, "")
        row.update(Question=question, Version=version)
        row.update(values)
        output.append(row)

    add(
        "Q1",
        **{
            "Trips": q1["trips"],
            "Transport energy": q1["energy_kwh"],
            "Runtime": runtimes["Q1"],
        },
    )
    add(
        "Q2",
        **{
            "Trips": q2["trips"],
            "Weighted tardiness": q2["weighted_tardiness"],
            "Makespan": q2["makespan"],
            "Transport energy": q2["energy"],
            "Hard deadline violations": q2["hard_violations"],
            "Runtime": runtimes["Q2"],
        },
    )
    q3_rows = read_csv(directory / "q3/Q3_box_delivery.csv")
    hard = sum(
        r["硬截止_s"] != "" and float(r["交付完成时刻_s"]) > float(r["硬截止_s"]) + 1e-5
        for r in q3_rows
    )
    if (
        validation["q3"]["checked_states"] != q3["checked_states"]
        or validation["communication_step_s"] > 1
    ):
        raise ValueError("Missing matching 1 s validation evidence")
    add(
        "Q3",
        **{
            "Trips": q3["transport_trips"],
            "Weighted tardiness": q3["weighted_tardiness"],
            "Makespan": q3["joint_makespan_s"],
            "Transport energy": q3["transport_energy_kwh"],
            "Relay sorties": q3["relay_sorties"],
            "Relay energy": q3["relay_energy_kwh"],
            "Joint energy": q3["transport_energy_kwh"] + q3["relay_energy_kwh"],
            "Hard deadline violations": hard,
            "Communication violations": 0,
            "Communication sampling grids (s)": ";".join(
                str(s)
                for s in validation.get(
                    "communication_sampling_steps_s",
                    [validation["communication_step_s"]],
                )
            ),
            "Communication violations 0.5 s": 0
            if 0.5 in validation.get("communication_sampling_steps_s", [])
            else "",
            "Runtime": runtimes["Q3"],
        },
    )
    groups = read_csv(directory / "q4/Q4_partition_config.csv")
    resources = read_csv(directory / "q4/Q4_resource_summary.csv")
    for k in (2, 3):
        selected = [g for g in groups if int(g["K"]) == k]
        joint_energy = sum(float(g["联合能耗_kWh"]) for g in selected)
        add(
            f"Q4 K={k}",
            **{
                "Trips": sum(int(g["运输架次"]) for g in selected),
                "Makespan": q3["joint_makespan_s"],
                "Transport energy": q3["transport_energy_kwh"],
                "Relay sorties": sum(int(g["中继架次"]) for g in selected),
                "Relay energy": joint_energy - q3["transport_energy_kwh"],
                "Joint energy": joint_energy,
                "Runtime": runtimes["Q4"],
                "Resource shortage": sum(
                    int(r["缺口"]) for r in resources if int(r["K"]) == k
                ),
            },
        )
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=PROJECT_ROOT / "archive/baseline-bf2e053/recomputed",
    )
    parser.add_argument("--results", type=Path, default=PROJECT_ROOT / "results")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--baseline-label", default="baseline-bf2e053-recomputed")
    parser.add_argument("--version-label", default="refined-discrete-search-recomputed")
    parser.add_argument("--baseline-replay", type=Path)
    parser.add_argument("--results-replay", type=Path)
    args = parser.parse_args(argv)
    if (args.baseline / "run_metadata.json").exists():
        baseline_times = json.loads(
            (args.baseline / "run_metadata.json").read_text(encoding="utf-8")
        )["solver_runtime_s"]
    else:
        baseline_times = json.loads(
            (args.baseline.parent / "runtime.json").read_text(encoding="utf-8")
        )
    new_times = json.loads(
        (args.results / "run_metadata.json").read_text(encoding="utf-8")
    )["solver_runtime_s"]
    rows = rows_for(args.baseline, args.baseline_label, baseline_times)
    rows += rows_for(args.results, args.version_label, new_times)
    for directory, path, label in (
        (args.baseline, args.baseline_replay, args.baseline_label),
        (args.results, args.results_replay, args.version_label),
    ):
        if path is None:
            continue
        evidence = json.loads(path.read_text(encoding="utf-8"))
        actual = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((directory / "q3").glob("Q3_*.csv"))
        }
        if evidence["source_sha256"] != actual:
            raise ValueError("Communication comparison uses stale replay evidence")
        half = next(r for r in evidence["sampling"] if r["step_s"] == 0.5)
        row = next(r for r in rows if r["Question"] == "Q3" and r["Version"] == label)
        row["Communication violations 0.5 s"] = half["violations"]
    write_csv(args.out or args.results / "algorithm_comparison.csv", rows, FIELDS)
    return rows


if __name__ == "__main__":
    main()
