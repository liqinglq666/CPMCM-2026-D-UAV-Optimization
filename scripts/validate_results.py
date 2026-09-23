from __future__ import annotations

# AI-assisted development disclosure
# Tool: ChatGPT
# Model: GPT-5.6 Sol
# Developer: OpenAI
# General-availability release date: 2026-07-09

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def intervals_overlap(a0, a1, b0, b1, eps=1e-9):
    return max(a0, b0) < min(a1, b1) - eps


def check_no_overlap(rows, resource_key, start_key, end_key, label):
    groups = defaultdict(list)
    for r in rows:
        groups[r[resource_key]].append(
            (float(r[start_key]), float(r[end_key]), r)
        )
    problems = []
    for resource, items in groups.items():
        items.sort(key=lambda x: x[0])
        for left, right in zip(items, items[1:]):
            if intervals_overlap(
                left[0], left[1], right[0], right[1]
            ):
                problems.append(
                    (label, resource, left[2], right[2])
                )
    return problems


def main():
    parser = argparse.ArgumentParser(
        description="Validate CPMCM 2026 D result CSVs"
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results",
    )
    args = parser.parse_args()
    root = args.results
    errors = []

    q2_box = read_csv(
        root / "q2" / "Q2_box_delivery_balanced.csv"
    )
    q2_ids = [r["货箱编号"] for r in q2_box]
    if len(q2_ids) != 80 or len(set(q2_ids)) != 80:
        errors.append(
            f"Q2 box coverage invalid: total={len(q2_ids)}, "
            f"unique={len(set(q2_ids))}"
        )
    for r in q2_box:
        hard = r.get("硬截止时间（s）", "")
        if (
            hard
            and float(r["交付完成时刻（s）"])
            > float(hard) + 1e-8
        ):
            errors.append(
                f"Q2 hard deadline violation: {r['货箱编号']}"
            )

    q3_box = read_csv(
        root / "q3" / "Q3_box_delivery.csv"
    )
    q3_ids = [r["货箱编号"] for r in q3_box]
    if len(q3_ids) != 80 or len(set(q3_ids)) != 80:
        errors.append(
            f"Q3 box coverage invalid: total={len(q3_ids)}, "
            f"unique={len(set(q3_ids))}"
        )
    if set(q3_ids) != set(q2_ids):
        errors.append("Q2 and Q3 cargo-box sets differ")

    for r in q3_box:
        hard = r.get("硬截止_s", "")
        if (
            hard
            and float(r["交付完成时刻_s"])
            > float(hard) + 1e-8
        ):
            errors.append(
                f"Q3 hard deadline violation: {r['货箱编号']}"
            )

    q3_trips = read_csv(
        root / "q3" / "Q3_transport_trips.csv"
    )
    errors.extend(
        check_no_overlap(
            q3_trips,
            "无人机编号",
            "开始时刻_s",
            "返回O01时刻_s",
            "transport UAV overlap",
        )
    )

    q3_relay = read_csv(
        root / "q3" / "Q3_relay_sorties.csv"
    )
    relay_groups = defaultdict(list)
    for r in q3_relay:
        relay_groups[r["中继无人机编号"]].append(
            (
                float(r["开始时刻_s"]),
                float(r["返回O01时刻_s"]) + 300.0,
                r["中继架次编号"],
            )
        )

    for uav, items in relay_groups.items():
        items.sort()
        for a, b in zip(items, items[1:]):
            if intervals_overlap(
                a[0], a[1], b[0], b[1]
            ):
                errors.append(
                    f"relay UAV overlap: {uav}, {a[2]}, {b[2]}"
                )

    components = [
        r["能源组件编号"]
        for r in q3_relay
    ]
    if len(components) != 6 or len(set(components)) != 6:
        errors.append(
            f"Q3 relay component usage unexpected: "
            f"{Counter(components)}"
        )

    q3_comm = read_csv(
        root / "q3" / "Q3_communication.csv"
    )
    relay_ids = {
        r["中继架次编号"]
        for r in q3_relay
    }
    trip_ids = {
        r["架次编号"]
        for r in q3_trips
    }
    for r in q3_comm:
        if r["运输架次编号"] not in trip_ids:
            errors.append(
                "Unknown Q3 transport trip in communication table: "
                + r["运输架次编号"]
            )
        if (
            r["保障方式"] == "中继"
            and r["中继架次编号"] not in relay_ids
        ):
            errors.append(
                f"Unknown relay sortie: {r['中继架次编号']}"
            )

    q4 = read_csv(
        root / "q4" / "Q4_resource_summary.csv"
    )
    for r in q4:
        inventory = int(r["现有库存"])
        need = int(r["分组独立执行总需求"])
        redundancy = int(r["冗余"])
        gap = int(r["缺口"])

        if (
            redundancy != max(0, inventory - need)
            or gap != max(0, need - inventory)
        ):
            errors.append(
                f"Q4 resource arithmetic mismatch: "
                f"K={r['K']} {r['资源']}"
            )

    gap_by_k = defaultdict(int)
    for r in q4:
        gap_by_k[int(r["K"])] += int(r["缺口"])

    print(
        "Q2 boxes:",
        len(q2_ids),
        "unique:",
        len(set(q2_ids)),
    )
    print(
        "Q3 boxes:",
        len(q3_ids),
        "unique:",
        len(set(q3_ids)),
    )
    print("Q3 transport trips:", len(q3_trips))
    print("Q3 relay sorties:", len(q3_relay))
    print(
        "Q4 total shortage units:",
        dict(sorted(gap_by_k.items())),
    )

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print("-", error)
        raise SystemExit(1)

    print("\nVALIDATION PASSED")


if __name__ == "__main__":
    main()
