# -*- coding: utf-8 -*-
"""
Q2 initial feasible-solution constructor.

AI-assisted development record:
- Tool: ChatGPT
- Model: GPT-5.6 Sol
- Developer: OpenAI

The participating team must independently verify every assumption, formula,
parameter, program output and final paper statement.

Rules implemented:
1. Each trip starts/ends at O01 and may visit multiple service areas.
2. Remaining payload is reduced after each service-area delivery.
3. Medical expected-delivery times are hard deadlines.
4. First-batch deadlines are hard deadlines.
5. Other expected-delivery times enter weighted tardiness.
6. A/B/C batteries are type-specific, shared within a type, and must recharge
   to 100% before reuse.
7. Battery recharge follows the two-stage rule in Appendix 2.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Dict, List, Tuple
from src.core.models import Box, DroneType, Trip
from src.core.inputs import load_inputs
from src.core.physics import Physics
from src.core.energy import charge_time
from src.core.routes import evaluate_route


def build_candidate(
    physics: Physics,
    drone_type: DroneType,
    start: float,
    order: Tuple[str, ...],
    remaining: Dict[str, Box],
    anchor_id: str,
):
    anchor = remaining[anchor_id]
    if anchor.service not in order:
        return None

    mass_left = drone_type.max_payload
    volume_left = drone_type.max_volume
    selected: Dict[str, List[Box]] = {s: [] for s in order}

    if anchor.mass > mass_left or anchor.volume > volume_left:
        return None

    selected[anchor.service].append(anchor)
    mass_left -= anchor.mass
    volume_left -= anchor.volume

    candidates = [
        b
        for b in remaining.values()
        if b.id != anchor_id and b.service in order
    ]

    def box_rank(b: Box):
        return (
            0 if b.hard_deadline is not None else 1,
            b.hard_deadline or 1e18,
            b.expected,
            -b.priority,
            -b.mass,
        )

    for box in sorted(candidates, key=box_rank):
        if (
            box.mass <= mass_left + 1e-9
            and box.volume <= volume_left + 1e-12
        ):
            selected[box.service].append(box)
            mass_left -= box.mass
            volume_left -= box.volume

    actual_order = tuple(s for s in order if selected[s])
    if not actual_order:
        return None

    def evaluate(sel, visit_order):
        trip_boxes = [b for s in visit_order for b in sel[s]]
        profile = evaluate_route(physics, drone_type.code, trip_boxes, visit_order)
        return (trip_boxes, {key: start + value for key, value in profile.delivery.items()},
                start + profile.duration, profile.energy)

    trip_boxes, delivery, end, energy = evaluate(
        selected,
        actual_order,
    )

    energy_limit = (
        1.0 - drone_type.rho
    ) * drone_type.energy_use

    while energy > energy_limit + 1e-10:
        droppable = [
            b for b in trip_boxes if b.id != anchor_id
        ]
        if not droppable:
            return None

        droppable.sort(
            key=lambda b: (
                b.hard_deadline is not None,
                -(b.hard_deadline or 0.0),
                -b.expected,
                b.priority,
                b.mass,
            )
        )
        remove = droppable[0]
        selected[remove.service] = [
            x
            for x in selected[remove.service]
            if x.id != remove.id
        ]
        actual_order = tuple(
            s for s in actual_order if selected[s]
        )
        trip_boxes, delivery, end, energy = evaluate(
            selected,
            actual_order,
        )

    hard_lateness = sum(
        max(
            0.0,
            delivery[b.id] - b.hard_deadline,
        )
        for b in trip_boxes
        if b.hard_deadline is not None
    )
    hard_misses = sum(
        delivery[b.id] > b.hard_deadline + 1e-9
        for b in trip_boxes
        if b.hard_deadline is not None
    )
    weighted_tardiness = sum(
        b.priority
        * max(0.0, delivery[b.id] - b.expected)
        for b in trip_boxes
    )
    hard_count = sum(
        b.hard_deadline is not None
        for b in trip_boxes
    )
    reward = sum(
        b.priority * (
            2.0 if b.hard_deadline is not None else 1.0
        )
        for b in trip_boxes
    )
    mass = sum(b.mass for b in trip_boxes)

    metrics = (
        hard_misses,
        hard_lateness,
        weighted_tardiness,
        hard_count,
        reward,
        mass,
        len(trip_boxes),
        delivery[anchor_id],
        end,
        energy,
    )
    return (
        metrics,
        actual_order,
        selected,
        delivery,
        end,
        energy,
    )


def solve(
    root: Path,
    max_stops: int = 3,
    verbose: bool = False,
):
    nodes, types, drones, batteries, boxes, dem_file = load_inputs(root)
    physics = Physics(nodes, types, dem_file)
    remaining = {b.id: b for b in boxes}
    trips: List[Trip] = []

    services = sorted({b.service for b in boxes})
    neighbors = {
        s: sorted(
            [x for x in services if x != s],
            key=lambda x: physics.segment(s, x).distance,
        )
        for s in services
    }

    while remaining:
        hard_remaining = [
            b
            for b in remaining.values()
            if b.hard_deadline is not None
        ]

        if hard_remaining:
            anchor = min(
                hard_remaining,
                key=lambda b: (
                    b.hard_deadline,
                    b.expected,
                    -b.priority,
                    b.id,
                ),
            )
            phase = "hard"
        else:
            anchor = min(
                remaining.values(),
                key=lambda b: (
                    b.expected,
                    -b.priority,
                    b.id,
                ),
            )
            phase = "soft"

        best = None

        for drone in drones:
            t = types[drone.type]
            battery = min(
                (
                    b
                    for b in batteries
                    if b.type == drone.type
                ),
                key=lambda b: b.available,
            )
            start = max(
                drone.available,
                battery.available,
            )

            remaining_services = sorted(
                {b.service for b in remaining.values()}
            )
            nearby = [
                x
                for x in neighbors[anchor.service]
                if x in remaining_services
            ][:6]

            sequences = {(anchor.service,)}
            for extra_count in range(1, max_stops):
                for comb in itertools.combinations(
                    nearby,
                    extra_count,
                ):
                    for perm in itertools.permutations(
                        (anchor.service,) + comb
                    ):
                        sequences.add(perm)

            local_best = None

            for order in sorted(sequences):
                candidate = build_candidate(
                    physics,
                    t,
                    start,
                    order,
                    remaining,
                    anchor.id,
                )
                if candidate is None or candidate[0][0] > 0:
                    continue

                (
                    metrics,
                    _,
                    _,
                    _,
                    candidate_end,
                    candidate_energy,
                ) = candidate
                (
                    hard_misses,
                    hard_lateness,
                    weighted_tardiness,
                    hard_count,
                    reward,
                    mass,
                    box_count,
                    _anchor_delivery,
                    _end,
                    _energy,
                ) = metrics

                if phase == "hard":
                    score = (
                        hard_misses,
                        hard_lateness,
                        -hard_count,
                        -mass,
                        weighted_tardiness,
                        candidate_end,
                        candidate_energy,
                    )
                else:
                    throughput = mass / max(
                        candidate_end,
                        1.0,
                    )
                    score = (
                        -throughput,
                        -mass,
                        -box_count,
                        weighted_tardiness / 1e5,
                        candidate_end,
                        candidate_energy,
                    )

                item = (
                    score,
                    candidate,
                    drone,
                    battery,
                    start,
                )
                if (
                    local_best is None
                    or score < local_best[0]
                ):
                    local_best = item

            if (
                local_best is not None
                and (
                    best is None
                    or local_best[0] < best[0]
                )
            ):
                best = local_best

        if best is None:
            raise RuntimeError(
                f"No feasible candidate for {anchor.id}"
            )

        _, candidate, drone, battery, start = best
        (
            _metrics,
            order,
            selected,
            delivery,
            end,
            energy,
        ) = candidate

        trip_id = f"Q2-{len(trips) + 1:03d}"
        box_ids: List[str] = []
        for service in order:
            for box in selected[service]:
                box_ids.append(box.id)
                remaining.pop(box.id)

        soc = 1.0 - energy / types[drone.type].energy_use

        trip = Trip(
            trip_id=trip_id,
            drone_id=drone.id,
            type=drone.type,
            battery_id=battery.id,
            start=start,
            stops=list(order),
            boxes_by_stop={
                s: [b.id for b in selected[s]]
                for s in order
            },
            delivery=delivery,
            end=end,
            energy=energy,
            soc=100.0 * soc,
        )
        trips.append(trip)

        drone.available = end
        battery.available = (
            end
            + charge_time(
                types[drone.type],
                soc,
            )
        )

        if verbose:
            print(
                trip_id,
                drone.id,
                drone.type,
                battery.id,
                round(start, 1),
                order,
                len(box_ids),
                round(end, 1),
                round(energy, 3),
                "remaining=",
                len(remaining),
            )

    box_map = {b.id: b for b in boxes}
    deliveries = []
    for trip in trips:
        for box_id, time_value in trip.delivery.items():
            box = box_map[box_id]
            deliveries.append(
                (
                    box_id,
                    trip.trip_id,
                    box.service,
                    time_value,
                    box.expected,
                    box.hard_deadline,
                    box.priority,
                )
            )

    hard_violations = [
        row
        for row in deliveries
        if row[5] is not None
        and row[3] > row[5] + 1e-9
    ]
    weighted_tardiness = sum(
        row[6] * max(0.0, row[3] - row[4])
        for row in deliveries
    )

    metrics = {
        "trips": len(trips),
        "makespan": max(t.end for t in trips),
        "energy": sum(t.energy for t in trips),
        "weighted_tardiness": weighted_tardiness,
        "hard_violations": len(hard_violations),
    }

    return {
        "trips": trips,
        "deliveries": deliveries,
        "drones": drones,
        "batteries": batteries,
        "boxes": boxes,
        "types": types,
        "physics": physics,
        "metrics": metrics,
    }

