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
from functools import lru_cache
from pathlib import Path
from typing import Dict, Sequence

from src.config import DEFAULT_DATA_ROOT
from src.core.inputs import load_inputs, load_relay_inputs
from src.core.energy import two_stage_charge_time
from src.core.io import write_csv, write_json
from .provenance import q3_fingerprints, check_task_relations, read_q3_relations
from src.core.constraints import max_overlap as max_overlap
from src.core.discrete import service_components
from src.core.provenance import save_provenance, check_question_provenance


def normalized_gini(values):
    """Normalized pairwise Gini, zero for no work or a single group."""
    values = list(values)
    if any(value < 0 for value in values):
        raise ValueError("Negative workload")
    total = sum(values)
    if len(values) < 2 or total == 0:
        return 0.0
    return sum(abs(a - b) for a in values for b in values) / (2 * (len(values) - 1) * total)


def atomic_components(transport_rows):
    return service_components(
        row["访问服务区顺序"].split("->") for row in transport_rows
    )


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
    from src.core.physics import Physics

    physics = Physics(_nodes, types, _dem)
    service_weights = defaultdict(int)
    for box in _boxes:
        service_weights[box.service] += 1

    @lru_cache(maxsize=None)
    def impedance(a, b):
        return (physics.flight_time("B", a, b) + physics.flight_time("B", b, a)) / 120
    relay_inputs = load_relay_inputs(root)
    inventory = {f"{code}_uav": sum(d.type == code for d in drones) for code in types}
    inventory.update(
        {f"{code}_bat": sum(b.type == code for b in batteries) for code in types}
    )
    inventory.update(
        relay_uav=len(relay_inputs.drone_ids),
        relay_comp=len(relay_inputs.component_ids),
    )
    transport, relay, communication, boxes = read_q3_relations(q3_dir)
    check_task_relations(transport, relay, communication, boxes)

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

    @lru_cache(maxsize=None)
    def group_stats(atom_indices: frozenset[int]):
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
        medoid, spatial = min(
            ((center, sum(service_weights[s] * impedance(center, s) for s in service_list))
             for center in service_list), key=lambda item: (item[1], item[0]))

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
            "transport_work_s": transport_busy,
            "relay_work_s": sum(float(row["返回O01时刻_s"]) - float(row["开始时刻_s"]) for row in rrows),
            "relay_service_s": relay_busy,
            "spatial_box_min": spatial,
            "medoid": medoid,
            "energy": energy,
        }

    def evaluate(labels: Sequence[int], k: int):
        groups = []
        for g in range(k):
            groups.append(
                group_stats(
                    frozenset(i for i, value in enumerate(labels) if value == g)
                )
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
    enumerated = {}
    balanced, balance_counts, strict_counts = {}, {}, {}
    tradeoffs, frontier = [], []

    for k in (2, 3):
        if k > len(atoms):
            raise ValueError(
                f"Cannot divide {len(atoms)} indivisible service atoms into {k} groups"
            )
        incumbent = None
        fair_incumbent = None
        enumerated[k] = 0
        balance_counts[k] = strict_counts[k] = 0
        # Explicit planning preferences taken from the reference comparison,
        # not additional official constraints. Original minimum-resource result
        # remains the primary output and is reported beside this alternative.
        min_size, max_size, max_gini = (6, 9, .33) if k == 2 else (4, 6, .34)
        candidates = []
        for labels in canonical_partitions(len(atoms), k):
            enumerated[k] += 1
            result = evaluate(labels, k)
            candidate = (result[0], labels, *result[1:])
            if incumbent is None or candidate[0] < incumbent[0]:
                incumbent = candidate
            groups = result[1]
            sizes = [len(g["services"]) for g in groups]
            gini = normalized_gini(g["transport_work_s"] for g in groups)
            spatial = sum(g["spatial_box_min"] for g in groups)
            metrics = (result[0][0], gini, spatial)
            candidates.append((metrics, labels, sum(g["energy"] for g in groups), sizes))
            relay_ids = [rid for g in groups for rid in g["relay_sortie_ids"]]
            if min(sizes) >= 2 and len(relay_ids) == len(set(relay_ids)):
                strict_counts[k] += 1
            if min(sizes) >= min_size and max(sizes) <= max_size and gini <= max_gini:
                balance_counts[k] += 1
                score = (result[0][0], result[0][1], gini, spatial)
                if fair_incumbent is None or score < fair_incumbent[0]:
                    fair_incumbent = (score, labels, *result[1:])
        best[k] = incumbent
        balanced[k] = fair_incumbent
        for policy, choice in (("minimum_resources", incumbent), ("balanced", fair_incumbent)):
            if choice is None:
                continue
            score, labels, groups, totals, gaps, redundancy = choice
            tradeoffs.append(dict(K=k, policy=policy, shortage=sum(gaps.values()),
                service_counts="/".join(str(len(g["services"])) for g in groups),
                box_counts="/".join(str(g["boxes"]) for g in groups),
                transport_gini=normalized_gini(g["transport_work_s"] for g in groups),
                spatial_box_min=sum(g["spatial_box_min"] for g in groups),
                energy_kwh=sum(g["energy"] for g in groups),
                extra_relay_sorties=sum(g["relay_sorties"] for g in groups) - len(relay)))
        # Keep only the discovered finite-input frontier in (gap,Gini,dispersion).
        nondominated = []
        for item in sorted(candidates):
            score = item[0]
            if any(all(a <= b for a, b in zip(old[0], score)) for old in nondominated):
                continue
            nondominated = [old for old in nondominated if not all(a <= b for a, b in zip(score, old[0]))]
            nondominated.append(item)
        frontier.extend(dict(K=k, shortage=s[0], transport_gini=s[1], spatial_box_min=s[2],
                             energy_kwh=energy, labels=list(labels), service_counts=sizes)
                        for s, labels, energy, sizes in nondominated)

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    config_rows = []
    resource_rows = []
    decomposition_rows = []
    pooled = group_stats(frozenset(range(len(atoms))))["req"]

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
            extra = totals[key] - pooled[key]
            headroom = inventory[key] - pooled[key]
            decomposition_rows.append(dict(
                K=k, resource=key, pooled_peak=pooled[key], inventory=inventory[key],
                independent_total=totals[key], inventory_headroom=headroom,
                transport_peak_separation=extra if not key.startswith("relay_") else 0,
                relay_independent_replication=extra if key.startswith("relay_") else 0,
                deficit=max(0, extra - headroom),
            ))
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

    write_csv(out_dir / "Q4_gap_decomposition.csv", decomposition_rows)
    fair_groups, fair_resources = [], []
    for k, choice in balanced.items():
        if choice is None:
            continue
        _score, _labels, groups, totals, gaps, _redundancy = choice
        for i, group in enumerate(groups, 1):
            fair_groups.append(dict(K=k, group=f"G{i}", services=",".join(group["services"]),
                boxes=group["boxes"], transport_trips=group["transport_trips"],
                relay_sorties=group["relay_sorties"], transport_work_s=group["transport_work_s"],
                relay_work_s=group["relay_work_s"], medoid=group["medoid"],
                spatial_box_min=group["spatial_box_min"], energy_kwh=group["energy"], **group["req"]))
        fair_resources.extend(dict(K=k, resource=key, inventory=inventory[key],
                                   required=totals[key], shortage=gaps[key]) for key in inventory)
    write_csv(out_dir / "Q4_preference_comparison.csv", tradeoffs)
    for name in ("Q4_balanced_groups.csv", "Q4_balanced_resources.csv"):
        (out_dir / name).unlink(missing_ok=True)
    if fair_groups:
        write_csv(out_dir / "Q4_balanced_groups.csv", fair_groups)
        write_csv(out_dir / "Q4_balanced_resources.csv", fair_resources)
    write_json(out_dir / "Q4_preference_frontier.json", frontier)
    write_json(out_dir / "Q4_policy_audit.json", dict(
        primary="minimum_resources", balanced_constraints={
            2: dict(min_services=6, max_services=9, maximum_transport_gini=.33),
            3: dict(min_services=4, max_services=6, maximum_transport_gini=.34)},
        balanced_feasible_partitions=balance_counts,
        strict_no_relay_copy_min_two_services_feasible_partitions=strict_counts,
        workload="transport preparation through return, excluding relay time from Gini",
        spatial="box-weighted medoid; bidirectional B-type flight time on unchanged official DEM",
        group_energy="unchanged transport plus full original relay copy for every dependent group",
        scope="exhaustive fixed-Q3 partitions; balance limits are declared preferences",
        source_fingerprints=q3_fingerprints(q3_dir)))
    write_json(out_dir / "Q4_enumeration_certificate.json", dict(
        atomic_components=atoms, atomic_component_count=len(atoms),
        enumerated_partitions=enumerated, total_partitions=sum(enumerated.values()),
        exactness="exhaustive unlabeled partitions conditional on frozen Q3 tasks",
        interval_convention="half-open; batteries include full recharge; relay UAVs include turnaround",
        source_fingerprints=q3_fingerprints(q3_dir),
    ))
    write_json(out_dir / "Q4_source_manifest.json", q3_fingerprints(q3_dir))
    save_provenance(root, out_dir)
    return {
        "atoms": atoms,
        "best": best,
        "config_rows": config_rows,
        "resource_rows": resource_rows,
    }
