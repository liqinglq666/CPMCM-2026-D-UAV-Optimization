# -*- coding: utf-8 -*-
"""
Q4 fixed-Q3 task partition and independent resource-sizing model.

Inputs are the finalized Q3 transport / relay / communication result CSVs.
All Q3 decisions are kept fixed. Multi-service transport trips induce
indivisible service-area components. K=2 and K=3 partitions of those
components are exhaustively enumerated.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

INVENTORY = {
    "A_uav": 4,
    "B_uav": 2,
    "C_uav": 2,
    "A_bat": 6,
    "B_bat": 4,
    "C_bat": 4,
    "relay_uav": 2,
    "relay_comp": 6,
}

CHARGE_TIME = {"A": 1800.0, "B": 2400.0, "C": 3000.0}
RELAY_CHARGE_TIME = 1800.0
RELAY_TURNAROUND = 300.0


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def two_stage_charge_time(
    full_charge_s: float,
    soc_percent: float,
) -> float:
    s = max(0.0, min(1.0, soc_percent / 100.0))
    if s < 0.90:
        return full_charge_s * (
            0.65 * (0.90 - s) / 0.90
            + 0.35
        )
    return (
        full_charge_s
        * 0.35
        * (1.0 - s) / 0.10
    )


def max_overlap(intervals: Iterable[Tuple[float, float]]) -> int:
    events = []
    for start, end in intervals:
        events.append((start, +1))
        events.append((end, -1))

    # End before start at the same instant allows immediate reuse.
    events.sort(key=lambda x: (x[0], x[1]))

    current = 0
    maximum = 0
    for _time, delta in events:
        current += delta
        maximum = max(maximum, current)
    return maximum


def atomic_components(transport_rows):
    services = sorted(
        {
            s
            for row in transport_rows
            for s in row["访问服务区顺序"].split("->")
        }
    )
    parent = {s: s for s in services}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for row in transport_rows:
        route = row["访问服务区顺序"].split("->")
        for a, b in zip(route, route[1:]):
            union(a, b)

    components = defaultdict(list)
    for service in services:
        components[find(service)].append(service)

    atoms = list(components.values())
    atoms.sort(key=lambda x: (-len(x), x))
    return atoms


def canonical_partitions(n: int, k: int):
    """Yield unlabeled set partitions encoded by integer labels."""
    labels = [0] * n

    def rec(i: int, max_label: int):
        if i == n:
            if max_label == k - 1:
                yield tuple(labels)
            return

        upper = min(max_label + 1, k - 1)
        for label in range(upper + 1):
            labels[i] = label
            yield from rec(
                i + 1,
                max(max_label, label),
            )

    labels[0] = 0
    yield from rec(1, 0)


def solve_partitions(
    q3_dir: Path,
    out_dir: Path,
):
    transport = _read_csv(
        q3_dir / "Q3_transport_trips.csv"
    )
    relay = _read_csv(
        q3_dir / "Q3_relay_sorties.csv"
    )
    communication = _read_csv(
        q3_dir / "Q3_communication.csv"
    )
    boxes = _read_csv(
        q3_dir / "Q3_box_delivery.csv"
    )

    atoms = atomic_components(transport)

    trip_services = {
        r["架次编号"]:
        set(r["访问服务区顺序"].split("->"))
        for r in transport
    }

    trip_relay = {
        r["运输架次编号"]: r["中继架次编号"]
        for r in communication
        if r["保障方式"] == "中继"
    }
    relay_map = {
        r["中继架次编号"]: r
        for r in relay
    }

    box_count_by_trip = defaultdict(int)
    for row in boxes:
        box_count_by_trip[row["架次编号"]] += 1

    trip_atom = {}
    for row in transport:
        trip_id = row["架次编号"]
        hits = [
            i
            for i, atom in enumerate(atoms)
            if trip_services[trip_id] <= set(atom)
        ]
        if len(hits) != 1:
            raise RuntimeError(
                f"{trip_id} is not contained in exactly one atom: {hits}"
            )
        trip_atom[trip_id] = hits[0]

    def group_stats(atom_indices: Set[int]):
        trip_ids = [
            row["架次编号"]
            for row in transport
            if trip_atom[row["架次编号"]] in atom_indices
        ]
        trows = [
            row
            for row in transport
            if row["架次编号"] in trip_ids
        ]

        relay_ids = sorted(
            {
                trip_relay[t]
                for t in trip_ids
                if t in trip_relay
            }
        )
        rrows = [
            relay_map[rid]
            for rid in relay_ids
        ]

        req: Dict[str, int] = {}

        for vehicle_type in ("A", "B", "C"):
            selected = [
                row
                for row in trows
                if row["机型编号"] == vehicle_type
            ]

            req[f"{vehicle_type}_uav"] = max_overlap(
                (
                    float(row["开始时刻_s"]),
                    float(row["返回O01时刻_s"]),
                )
                for row in selected
            )

            req[f"{vehicle_type}_bat"] = max_overlap(
                (
                    float(row["开始时刻_s"]),
                    float(row["返回O01时刻_s"])
                    + two_stage_charge_time(
                        CHARGE_TIME[vehicle_type],
                        float(row["返航SOC_pct"]),
                    ),
                )
                for row in selected
            )

        req["relay_uav"] = max_overlap(
            (
                float(row["开始时刻_s"]),
                float(row["返回O01时刻_s"])
                + RELAY_TURNAROUND,
            )
            for row in rrows
        )

        req["relay_comp"] = max_overlap(
            (
                float(row["开始时刻_s"]),
                float(row["返回O01时刻_s"])
                + two_stage_charge_time(
                    RELAY_CHARGE_TIME,
                    float(row["返航SOC_pct"]),
                ),
            )
            for row in rrows
        )

        service_list = sorted(
            {
                service
                for i in atom_indices
                for service in atoms[i]
            }
        )

        transport_busy = sum(
            float(row["返回O01时刻_s"])
            - float(row["开始时刻_s"])
            for row in trows
        )
        relay_busy = sum(
            float(row["服务结束时刻_s"])
            - float(row["建链完成时刻_s"])
            for row in rrows
        )
        energy = (
            sum(
                float(row["架次能耗_kWh"])
                for row in trows
            )
            + sum(
                float(row["架次能耗_kWh"])
                for row in rrows
            )
        )

        return {
            "atoms": tuple(sorted(atom_indices)),
            "services": service_list,
            "transport_trip_ids": trip_ids,
            "relay_sortie_ids": relay_ids,
            "req": req,
            "transport_trips": len(trip_ids),
            "relay_sorties": len(relay_ids),
            "boxes": sum(
                box_count_by_trip[t]
                for t in trip_ids
            ),
            "work": transport_busy + relay_busy,
            "energy": energy,
        }

    def evaluate(labels: Sequence[int], k: int):
        groups = []
        for g in range(k):
            groups.append(
                group_stats(
                    {
                        i
                        for i, value in enumerate(labels)
                        if value == g
                    }
                )
            )

        totals = {
            key: sum(
                group["req"][key]
                for group in groups
            )
            for key in INVENTORY
        }
        gaps = {
            key: max(
                0,
                totals[key] - INVENTORY[key],
            )
            for key in INVENTORY
        }
        redundancy = {
            key: max(
                0,
                INVENTORY[key] - totals[key],
            )
            for key in INVENTORY
        }

        gap_sum = sum(gaps.values())
        total_resources = sum(totals.values())

        works = [g["work"] for g in groups]
        mean_work = sum(works) / k
        cv = (
            (
                sum(
                    (w - mean_work) ** 2
                    for w in works
                )
                / k
            ) ** 0.5
            / mean_work
            if mean_work
            else 0.0
        )

        trips = [
            g["transport_trips"]
            for g in groups
        ]
        trip_imbalance = max(trips) - min(trips)

        # Lexicographic objective.
        score = (
            gap_sum,
            total_resources,
            cv,
            trip_imbalance,
        )
        return (
            score,
            groups,
            totals,
            gaps,
            redundancy,
        )

    best = {}

    for k in (2, 3):
        candidates = []
        for labels in canonical_partitions(
            len(atoms), k
        ):
            if len(set(labels)) < k:
                continue

            result = evaluate(labels, k)
            candidates.append(
                (
                    result[0],
                    labels,
                    *result[1:],
                )
            )

        candidates.sort(key=lambda x: x[0])
        best[k] = candidates[0]

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    config_rows = []
    resource_rows = []

    for k in (2, 3):
        (
            score,
            labels,
            groups,
            totals,
            gaps,
            redundancy,
        ) = best[k]

        for index, group in enumerate(
            groups,
            start=1,
        ):
            req = group["req"]
            config_rows.append(
                {
                    "K": k,
                    "任务组编号": f"G{index}",
                    "服务区列表": ",".join(
                        group["services"]
                    ),
                    "A型运输无人机数": req["A_uav"],
                    "B型运输无人机数": req["B_uav"],
                    "C型运输无人机数": req["C_uav"],
                    "A型电池组数": req["A_bat"],
                    "B型电池组数": req["B_bat"],
                    "C型电池组数": req["C_bat"],
                    "中继无人机数": req["relay_uav"],
                    "中继能源组件数": req["relay_comp"],
                    "运输架次": group["transport_trips"],
                    "中继架次": group["relay_sorties"],
                    "货箱数": group["boxes"],
                    "工作量_s": group["work"],
                    "联合能耗_kWh": group["energy"],
                }
            )

        for key in INVENTORY:
            resource_rows.append(
                {
                    "K": k,
                    "资源": key,
                    "现有库存": INVENTORY[key],
                    "分组独立执行总需求": totals[key],
                    "冗余": redundancy[key],
                    "缺口": gaps[key],
                }
            )

    for filename, rows in (
        ("Q4_partition_config.csv", config_rows),
        ("Q4_resource_summary.csv", resource_rows),
    ):
        with (
            out_dir / filename
        ).open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=rows[0].keys(),
            )
            writer.writeheader()
            writer.writerows(rows)

    return {
        "atoms": atoms,
        "best": best,
        "config_rows": config_rows,
        "resource_rows": resource_rows,
    }
