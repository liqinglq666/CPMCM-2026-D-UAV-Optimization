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
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import rasterio
from pyproj import Geod
from rasterio.features import geometry_mask
from shapely.geometry import LineString

G = 9.80665
GEOD = Geod(ellps="WGS84")


def decode_hash_u(text: str) -> str:
    return re.sub(
        r"#U([0-9a-fA-F]{4})",
        lambda m: chr(int(m.group(1), 16)),
        text,
    )


def find_file(root: Path, keyword: str, suffix: str = ".xlsx") -> Path:
    for p in root.rglob(f"*{suffix}"):
        if keyword in decode_hash_u(p.name):
            return p
    raise FileNotFoundError(keyword)


@dataclass(frozen=True)
class Node:
    code: str
    lon: float
    lat: float
    elev: float


@dataclass(frozen=True)
class DroneType:
    code: str
    empty_mass: float
    max_payload: float
    max_volume: float
    cruise_speed: float
    range_empty: float
    range_full: float
    energy_use: float
    rho: float
    prep: float
    load_per_box: float
    hand_base: float
    hand_per_box: float
    climb_speed: float
    descent_speed: float
    eta_up: float
    full_charge: float


@dataclass(frozen=True)
class Box:
    id: str
    service: str
    kind: str
    mass: float
    volume: float
    first: bool
    first_deadline: Optional[float]
    expected: float
    priority: float
    hard_deadline: Optional[float]


@dataclass(frozen=True)
class Segment:
    a: str
    b: str
    distance: float
    cruise_alt: float
    climb: float
    descent: float


@dataclass
class Resource:
    id: str
    type: str
    available: float = 0.0


@dataclass
class Trip:
    trip_id: str
    drone_id: str
    type: str
    battery_id: str
    start: float
    stops: List[str]
    boxes_by_stop: Dict[str, List[str]]
    delivery: Dict[str, float]
    end: float
    energy: float
    soc: float


def load_inputs(root: Path):
    node_file = find_file(root, "调度中心与服务区")
    node_df = pd.read_excel(node_file, sheet_name="数据", header=None)
    nodes: Dict[str, Node] = {}
    for i in [2] + list(range(6, 21)):
        r = node_df.iloc[i]
        nodes[str(r.iloc[0])] = Node(
            str(r.iloc[0]),
            float(r.iloc[2]),
            float(r.iloc[3]),
            float(r.iloc[4]),
        )

    drone_file = find_file(root, "运输无人机数据")
    d = pd.read_excel(drone_file, sheet_name="数据", header=None)
    header = list(d.iloc[1])
    types: Dict[str, DroneType] = {}
    for i in range(2, 5):
        r = dict(zip(header, d.iloc[i]))
        code = str(r["机型编号"])
        types[code] = DroneType(
            code=code,
            empty_mass=float(r["含电池空载总质量（kg）"]),
            max_payload=float(r["最大载货质量（kg）"]),
            max_volume=float(r["可用装载体积（m³）"]),
            cruise_speed=float(r["计划巡航速度（m/s）"]),
            range_empty=float(r["空载标准航程（m）"]),
            range_full=float(r["满载标准航程（m）"]),
            energy_use=float(r["电池可用能量（kWh）"]),
            rho=float(r["返航电量下限（%）"]) / 100.0,
            prep=float(r["工位固定准备时间（s）"]),
            load_per_box=float(r["每箱装载时间（s）"]),
            hand_base=float(r["接收点基础交接时间（s）"]),
            hand_per_box=float(r["每箱增加交接时间（s）"]),
            climb_speed=float(r["最大爬升速度（m/s）"]),
            descent_speed=float(r["最大下降速度（m/s）"]),
            eta_up=float(r["爬升能耗效率"]),
            full_charge=0.0,
        )

    for i in range(19, 22):
        code = str(d.iloc[i, 0])
        old = types[code]
        types[code] = DroneType(
            **{**old.__dict__, "full_charge": float(d.iloc[i, 2])}
        )

    drones: List[Resource] = []
    for i in range(8, 16):
        if pd.notna(d.iloc[i, 0]):
            drones.append(
                Resource(str(d.iloc[i, 0]), str(d.iloc[i, 1]), 0.0)
            )

    batteries: List[Resource] = []
    counts = {"A": 6, "B": 4, "C": 4}
    for code, count in counts.items():
        for j in range(1, count + 1):
            batteries.append(Resource(f"{code}-BAT-{j:02d}", code, 0.0))

    demand_file = find_file(root, "物资需求与配送时限")
    box_df = pd.read_excel(demand_file, sheet_name="逐箱货箱清单")
    boxes: List[Box] = []
    for _, r in box_df.iterrows():
        kind = str(r["物资类型"])
        first = str(r["是否首批保障"]) == "是"
        first_deadline = (
            None
            if pd.isna(r["首批截止时间（s）"])
            else float(r["首批截止时间（s）"])
        )
        expected = float(r["期望送达时间（s）"])

        hard_deadline: Optional[float]
        hard_deadline = expected if kind == "医疗物资" else None
        if first and first_deadline is not None:
            hard_deadline = (
                first_deadline
                if hard_deadline is None
                else min(hard_deadline, first_deadline)
            )

        boxes.append(
            Box(
                id=str(r["货箱编号"]),
                service=str(r["服务区编号"]),
                kind=kind,
                mass=float(r["单箱质量（kg）"]),
                volume=float(r["单箱体积（m³）"]),
                first=first,
                first_deadline=first_deadline,
                expected=expected,
                priority=float(r["应急优先系数"]),
                hard_deadline=hard_deadline,
            )
        )

    dem_file = find_file(root, "30米DEM", ".tif")
    return nodes, types, drones, batteries, boxes, dem_file


class Physics:
    def __init__(
        self,
        nodes: Dict[str, Node],
        types: Dict[str, DroneType],
        dem_file: Path,
    ):
        self.nodes = nodes
        self.types = types
        self.dem_file = dem_file
        self._cache: Dict[Tuple[str, str], Segment] = {}
        self.ds = rasterio.open(dem_file)
        self.dem = self.ds.read(1)

    def segment(self, a: str, b: str) -> Segment:
        key = (a, b)
        if key in self._cache:
            return self._cache[key]

        node_a = self.nodes[a]
        node_b = self.nodes[b]
        _, _, distance = GEOD.inv(
            node_a.lon,
            node_a.lat,
            node_b.lon,
            node_b.lat,
        )
        line = LineString(
            [(node_a.lon, node_a.lat), (node_b.lon, node_b.lat)]
        )
        mask = geometry_mask(
            [line.__geo_interface__],
            out_shape=(self.ds.height, self.ds.width),
            transform=self.ds.transform,
            invert=True,
            all_touched=True,
        )
        max_dem = float(np.max(self.dem[mask]))
        cruise_alt = max_dem + 50.0

        altitude_a = node_a.elev + (0.0 if a == "O01" else 30.0)
        altitude_b = node_b.elev + (0.0 if b == "O01" else 30.0)

        seg = Segment(
            a=a,
            b=b,
            distance=float(distance),
            cruise_alt=cruise_alt,
            climb=max(0.0, cruise_alt - altitude_a),
            descent=max(0.0, cruise_alt - altitude_b),
        )
        self._cache[key] = seg
        return seg

    def equivalent_range(self, type_code: str, payload: float) -> float:
        t = self.types[type_code]
        return t.range_empty - (
            t.range_empty - t.range_full
        ) * (payload / t.max_payload) ** 1.5

    def energy(
        self,
        type_code: str,
        a: str,
        b: str,
        payload: float,
    ) -> float:
        t = self.types[type_code]
        seg = self.segment(a, b)
        e_horizontal = (
            t.energy_use
            * seg.distance
            / self.equivalent_range(type_code, payload)
        )
        e_climb = (
            (t.empty_mass + payload)
            * G
            * seg.climb
            / (t.eta_up * 3.6e6)
        )
        return e_horizontal + e_climb

    def flight_time(self, type_code: str, a: str, b: str) -> float:
        t = self.types[type_code]
        seg = self.segment(a, b)
        return (
            seg.climb / t.climb_speed
            + seg.distance / t.cruise_speed
            + seg.descent / t.descent_speed
        )


def charge_time(t: DroneType, soc: float) -> float:
    s = max(0.0, min(1.0, soc))
    if s < 0.90:
        return t.full_charge * (
            0.65 * (0.90 - s) / 0.90 + 0.35
        )
    return t.full_charge * 0.35 * (1.0 - s) / 0.10


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
        payload = sum(b.mass for b in trip_boxes)
        now = (
            start
            + drone_type.prep
            + drone_type.load_per_box * len(trip_boxes)
        )
        energy = 0.0
        delivery: Dict[str, float] = {}
        prev = "O01"
        remaining_payload = payload

        for service in visit_order:
            energy += physics.energy(
                drone_type.code,
                prev,
                service,
                remaining_payload,
            )
            now += physics.flight_time(
                drone_type.code,
                prev,
                service,
            )
            now += (
                drone_type.hand_base
                + drone_type.hand_per_box * len(sel[service])
            )
            for box in sel[service]:
                delivery[box.id] = now
            remaining_payload -= sum(
                b.mass for b in sel[service]
            )
            prev = service

        energy += physics.energy(
            drone_type.code,
            prev,
            "O01",
            0.0,
        )
        now += physics.flight_time(
            drone_type.code,
            prev,
            "O01",
        )
        return trip_boxes, delivery, now, energy

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
                if candidate is None:
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
                remaining.pop(box.id, None)

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
