# -*- coding: utf-8 -*-
"""
Q4 fixed-Q3 task partition and independent resource-sizing model.

Inputs are the finalized Q3 transport / relay / communication result CSVs.
All Q3 decisions are kept fixed. Multi-service transport trips induce
indivisible service-area components. K=2 and K=3 partitions of those
components are exhaustively enumerated.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Sequence, Set, Tuple

from src.config import DEFAULT_DATA_ROOT
from src.core.inputs import load_inputs, load_relay_inputs
from src.core.energy import two_stage_charge_time
from src.core.io import read_csv as _read_csv, write_csv
from src.core.numeric import finite
from src.core.provenance import save_provenance, check_question_provenance


def max_overlap(intervals: Iterable[Tuple[float, float]]) -> int:
    events = []
    for start, end in intervals:
        finite(start, "interval start", 0)
        finite(end, "interval end", start)
        if start == end:
            continue
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
        {s for row in transport_rows for s in row["访问服务区顺序"].split("->")}
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
    if not isinstance(n, int) or not isinstance(k, int) or n < 1 or not 1 <= k <= n:
        raise ValueError("Partition requires integers 1 <= k <= n")
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
    root: Path = DEFAULT_DATA_ROOT,
):
    check_question_provenance(root, q3_dir)
    _nodes, types, drones, batteries, _boxes, _dem = load_inputs(root)
    relay_inputs = load_relay_inputs(root)
    inventory = {f"{code}_uav": sum(d.type == code for d in drones) for code in types}
    inventory.update(
        {f"{code}_bat": sum(b.type == code for b in batteries) for code in types}
    )
    inventory.update(
        relay_uav=len(relay_inputs.drone_ids),
        relay_comp=len(relay_inputs.component_ids),
    )
    transport = _read_csv(q3_dir / "Q3_transport_trips.csv")
    relay = _read_csv(q3_dir / "Q3_relay_sorties.csv")
    communication = _read_csv(q3_dir / "Q3_communication.csv")
    boxes = _read_csv(q3_dir / "Q3_box_delivery.csv")

    atoms = atomic_components(transport)

    trip_services = {
        r["架次编号"]: set(r["访问服务区顺序"].split("->")) for r in transport
    }

    trip_relay = {
        r["运输架次编号"]: r["中继架次编号"]
        for r in communication
        if r["保障方式"] == "中继"
    }
    relay_map = {r["中继架次编号"]: r for r in relay}

    box_count_by_trip = defaultdict(int)
    for row in boxes:
        box_count_by_trip[row["架次编号"]] += 1

    trip_atom = {}
    for row in transport:
        trip_id = row["架次编号"]
        hits = [
            i for i, atom in enumerate(atoms) if trip_services[trip_id] <= set(atom)
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
        trows = [row for row in transport if row["架次编号"] in trip_ids]

        relay_ids = sorted({trip_relay[t] for t in trip_ids if t in trip_relay})
        rrows = [relay_map[rid] for rid in relay_ids]

        req: Dict[str, int] = {}

        for vehicle_type in types:
            selected = [row for row in trows if row["机型编号"] == vehicle_type]

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
                        types[vehicle_type].full_charge,
                        float(row["返航SOC_pct"]) / 100,
                    ),
                )
                for row in selected
            )

        req["relay_uav"] = max_overlap(
            (
                float(row["开始时刻_s"]),
                float(row["返回O01时刻_s"]) + relay_inputs.spec.turnaround_s,
            )
            for row in rrows
        )

        req["relay_comp"] = max_overlap(
            (
                float(row["开始时刻_s"]),
                float(row["返回O01时刻_s"])
                + two_stage_charge_time(
                    relay_inputs.full_charge_s,
                    float(row["返航SOC_pct"]) / 100,
                ),
            )
            for row in rrows
        )

        service_list = sorted({service for i in atom_indices for service in atoms[i]})

        transport_busy = sum(
            float(row["返回O01时刻_s"]) - float(row["开始时刻_s"]) for row in trows
        )
        relay_busy = sum(
            float(row["服务结束时刻_s"]) - float(row["建链完成时刻_s"]) for row in rrows
        )
        energy = sum(float(row["架次能耗_kWh"]) for row in trows) + sum(
            float(row["架次能耗_kWh"]) for row in rrows
        )

        return {
            "atoms": tuple(sorted(atom_indices)),
            "services": service_list,
            "transport_trip_ids": trip_ids,
            "relay_sortie_ids": relay_ids,
            "req": req,
            "transport_trips": len(trip_ids),
            "relay_sorties": len(relay_ids),
            "boxes": sum(box_count_by_trip[t] for t in trip_ids),
            "work": transport_busy + relay_busy,
            "energy": energy,
        }

    def evaluate(labels: Sequence[int], k: int):
        groups = []
        for g in range(k):
            groups.append(
                group_stats({i for i, value in enumerate(labels) if value == g})
            )

        totals = {key: sum(group["req"][key] for group in groups) for key in inventory}
        gaps = {
            key: max(
                0,
                totals[key] - inventory[key],
            )
            for key in inventory
        }
        redundancy = {
            key: max(
                0,
                inventory[key] - totals[key],
            )
            for key in inventory
        }

        gap_sum = sum(gaps.values())
        total_resources = sum(totals.values())

        works = [g["work"] for g in groups]
        mean_work = sum(works) / k
        cv = (
            (sum((w - mean_work) ** 2 for w in works) / k) ** 0.5 / mean_work
            if mean_work
            else 0.0
        )

        trips = [g["transport_trips"] for g in groups]
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
        if k > len(atoms):
            raise ValueError(
                f"Cannot divide {len(atoms)} indivisible service atoms into {k} groups"
            )
        candidates = []
        for labels in canonical_partitions(len(atoms), k):
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
                    "服务区列表": ",".join(group["services"]),
                    **{f"{code}型运输无人机数": req[f"{code}_uav"] for code in types},
                    **{f"{code}型电池组数": req[f"{code}_bat"] for code in types},
                    "中继无人机数": req["relay_uav"],
                    "中继能源组件数": req["relay_comp"],
                    "运输架次": group["transport_trips"],
                    "中继架次": group["relay_sorties"],
                    "货箱数": group["boxes"],
                    "工作量_s": group["work"],
                    "联合能耗_kWh": group["energy"],
                }
            )

        for key in inventory:
            resource_rows.append(
                {
                    "K": k,
                    "资源": key,
                    "现有库存": inventory[key],
                    "分组独立执行总需求": totals[key],
                    "冗余": redundancy[key],
                    "缺口": gaps[key],
                }
            )

    for filename, rows in (
        ("Q4_partition_config.csv", config_rows),
        ("Q4_resource_summary.csv", resource_rows),
    ):
        write_csv(out_dir / filename, rows)

    save_provenance(root, out_dir)
    return {
        "atoms": atoms,
        "best": best,
        "config_rows": config_rows,
        "resource_rows": resource_rows,
    }
