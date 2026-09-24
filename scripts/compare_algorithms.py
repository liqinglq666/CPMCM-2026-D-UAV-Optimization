"""Compare validated, actually recomputed algorithm generations (seconds, kWh).

Blank cells are not applicable, not an invented zero. Q1 has no scheduled
makespan/deadlines. Q2 has no radio requirement. Q4 copies finalized Q3 times
and sizes independent resources; repeated relay sorties are counted per group.
"""

import argparse
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
    args = parser.parse_args(argv)
    baseline_times = json.loads(
        (args.baseline.parent / "runtime.json").read_text(encoding="utf-8")
    )
    new_times = json.loads(
        (args.results / "run_metadata.json").read_text(encoding="utf-8")
    )["solver_runtime_s"]
    rows = rows_for(args.baseline, "baseline-bf2e053-recomputed", baseline_times)
    rows += rows_for(args.results, "discrete-search-recomputed", new_times)
    write_csv(args.out or args.results / "algorithm_comparison.csv", rows, FIELDS)
    return rows


if __name__ == "__main__":
    main()
